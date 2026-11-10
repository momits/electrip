//! Discovery of the session host (N-03, ADR 0010): each instance announces
//! itself per mDNS as `_electrip._tcp` with its instance id, the protocol
//! version, the id of its command station and its status. A starting
//! instance searches for the host of its command station.

use electrip_core::session::Station;
use electrip_core::station::StationKind;
use mdns_sd::{RecvTimeoutError, ResolvedService, ServiceDaemon, ServiceEvent, ServiceInfo};
use std::collections::HashMap;
use std::collections::hash_map::RandomState;
use std::hash::BuildHasher;
use std::io;
use std::net::{Ipv4Addr, SocketAddr, ToSocketAddrs, UdpSocket};
use std::time::{Duration, Instant};

use crate::VERSION;

const SERVICE: &str = "_electrip._tcp.local.";

/// How long a starting instance searches for a host (ADR 0010).
const SEARCH: Duration = Duration::from_secs(2);

/// How long an instance waits after the search for a searching instance
/// with a smaller id to become host; after that it is host itself.
const PATIENCE: Duration = Duration::from_secs(4);

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Status {
    Searching,
    Host,
    Client,
}

impl Status {
    fn name(self) -> &'static str {
        match self {
            Status::Searching => "searching",
            Status::Host => "host",
            Status::Client => "client",
        }
    }
}

/// What another instance announces.
#[derive(Debug, Clone, PartialEq)]
struct Announcement {
    instance: u64,
    station: String,
    status: Status,
    address: SocketAddr,
}

#[derive(Debug, PartialEq)]
enum Election {
    Connect(SocketAddr),
    Host,
    /// A searching instance with a smaller id becomes host.
    Wait,
}

/// Connects to the host of `station`; of two hosts to the one with the
/// smaller id. Without a host the searching instance with the smallest id
/// becomes host, so instances that start together find one host.
fn elect(me: u64, station: &str, seen: &[Announcement]) -> Election {
    let same = |status| {
        seen.iter()
            .filter(move |a| a.station == station && a.status == status && a.instance != me)
    };
    match same(Status::Host).min_by_key(|a| a.instance) {
        Some(host) => Election::Connect(host.address),
        None if same(Status::Searching).any(|a| a.instance < me) => Election::Wait,
        None => Election::Host,
    }
}

/// The id of the command station (ADR 0010): the serial number of a Z21,
/// else its address, port and bus. A command station on this computer has
/// the LAN address of the computer, so it differs from the one on another
/// computer.
pub fn station_id(station: &Station) -> String {
    if station.kind == StationKind::Z21 {
        match electrip_station_z21::serial_number(&station.host, station.port) {
            Ok(serial) => return format!("z21:{serial}"),
            Err(e) => eprintln!("ERROR the Z21 has no id, its address stands in: {e}"),
        }
    }
    let ip = (station.host.as_str(), station.port)
        .to_socket_addrs()
        .ok()
        .and_then(|mut addresses| addresses.find(SocketAddr::is_ipv4))
        .map(|address| address.ip());
    let ip = match ip {
        Some(ip) if ip.is_loopback() => lan_ip().unwrap_or(ip).to_string(),
        Some(ip) => ip.to_string(),
        None => station.host.clone(),
    };
    format!("{ip}:{}:{}", station.port, station.bus)
}

const MDNS: (Ipv4Addr, u16) = (Ipv4Addr::new(224, 0, 0, 251), 5353);

/// An address outside the LAN (TEST-NET-1), for the unicast route.
const OUTSIDE: (Ipv4Addr, u16) = (Ipv4Addr::new(192, 0, 2, 1), 9);

/// The address this computer sends mDNS from, else the one of its default
/// route, since Windows may send multicast over loopback; no packet is
/// sent.
fn lan_ip() -> Option<std::net::IpAddr> {
    [MDNS, OUTSIDE].into_iter().find_map(|target| {
        let socket = UdpSocket::bind((Ipv4Addr::UNSPECIFIED, 0)).ok()?;
        socket.connect(target).ok()?;
        let ip = socket.local_addr().ok()?.ip();
        (!ip.is_loopback()).then_some(ip)
    })
}

/// Fails without access to the local network, e.g. on macOS without the
/// permission, where the mDNS daemon only logs its failed sends.
fn check_network() -> io::Result<()> {
    let socket = UdpSocket::bind((Ipv4Addr::UNSPECIFIED, 0))?;
    // An mDNS header without questions, which receivers ignore.
    socket
        .send_to(&[0; 12], MDNS)
        .map_err(|e| io::Error::other(format!("no access to the local network: {e}")))?;
    Ok(())
}

/// The announcement of this instance; it lasts as long as the value.
pub struct Discovery {
    daemon: ServiceDaemon,
    instance: u64,
    station: String,
}

impl Discovery {
    /// Announces the instance with a random id as searching.
    pub fn start(station: String) -> io::Result<Discovery> {
        check_network()?;
        let discovery = Discovery {
            daemon: ServiceDaemon::new().map_err(io::Error::other)?,
            instance: RandomState::new().hash_one(()),
            station,
        };
        discovery.announce(Status::Searching, 0)?;
        Ok(discovery)
    }

    /// Announces the status and the port of the control channel.
    pub fn announce(&self, status: Status, port: u16) -> io::Result<()> {
        let name = format!("{:016x}", self.instance);
        let version = VERSION.to_string();
        let properties = [
            ("id", name.as_str()),
            ("version", &version),
            ("station", &self.station),
            ("status", status.name()),
        ];
        let host_name = format!("{name}.local.");
        let info = ServiceInfo::new(SERVICE, &name, &host_name, "", port, &properties[..])
            .map_err(io::Error::other)?;
        let info = info.enable_addr_auto();
        self.daemon.register(info).map_err(io::Error::other)
    }

    /// Searches for the host of the command station, apart from the one
    /// at `gone`, whose announcement can outlive it; `None` if this
    /// instance is to be host.
    pub fn find_host(&self, gone: Option<SocketAddr>) -> io::Result<Option<SocketAddr>> {
        let events = self.daemon.browse(SERVICE).map_err(io::Error::other)?;
        let start = Instant::now();
        let mut seen = HashMap::new();
        let found = loop {
            match events.recv_timeout(Duration::from_millis(100)) {
                Ok(ServiceEvent::ServiceResolved(service)) => {
                    if let Some(announcement) =
                        announcement(&service).filter(|a| Some(a.address) != gone)
                    {
                        seen.insert(service.fullname, announcement);
                    }
                }
                Ok(ServiceEvent::ServiceRemoved(_, name)) => {
                    seen.remove(&name);
                }
                Err(RecvTimeoutError::Disconnected) => {
                    return Err(io::Error::other("the mDNS daemon stopped"));
                }
                _ => {}
            }
            let seen: Vec<_> = seen.values().cloned().collect();
            let waited = start.elapsed();
            match elect(self.instance, &self.station, &seen) {
                Election::Connect(host) => break Some(host),
                Election::Host if waited >= SEARCH => break None,
                Election::Wait if waited >= SEARCH + PATIENCE => break None,
                _ => {}
            }
        };
        self.daemon.stop_browse(SERVICE).map_err(io::Error::other)?;
        Ok(found)
    }
}

/// The announcement of an instance with the same protocol version.
fn announcement(service: &ResolvedService) -> Option<Announcement> {
    let property = |key| service.get_property_val_str(key);
    if property("version")? != VERSION.to_string() {
        return None;
    }
    let status = [Status::Searching, Status::Host, Status::Client]
        .into_iter()
        .find(|s| Some(s.name()) == property("status"))?;
    let ip = service.get_addresses_v4().into_iter().next()?;
    Some(Announcement {
        instance: u64::from_str_radix(property("id")?, 16).ok()?,
        station: property("station")?.to_string(),
        status,
        address: SocketAddr::from((ip, service.port)),
    })
}

#[cfg(test)]
mod tests;
