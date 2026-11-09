//! Electrip 2. The window is a client of the control channel on localhost
//! (N-08); without a display or with `--headless` the app runs without it.
//! The instance is the session host or a client of the host it finds per
//! mDNS or at `--host` (N-03).

use electrip_audio::{MixerDeviceSink, Speaker};
use electrip_control::{Discovery, Status, station_id};
use electrip_core::host::{Driver, Host};
use electrip_core::session::{Command, Station};
use electrip_core::station::StationKind;
use electrip_input::Gamepads;
use electrip_station_srcp::SrcpStation;
use electrip_station_z21::Z21Station;
use std::env;
use std::io;
use std::net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream, ToSocketAddrs};
use std::path::PathBuf;
use std::process::ExitCode;
use std::thread;
use std::time::Duration;

const DEFAULT_CONTROL_PORT: u16 = 4711;

/// How long the instance waits for the host at `--host` (N-03).
const HOST_TIMEOUT: Duration = Duration::from_secs(2);

const USAGE: &str = "usage: electrip [--headless] [--control-port <port>] [--library <dir>] [-f|--file <configuration>] [--host <address:port>] [--no-discovery]";

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("ERROR {e}");
            ExitCode::FAILURE
        }
    }
}

struct Args {
    control_port: u16,
    library: Option<PathBuf>,
    /// The configuration to open instead of the first one (B-24).
    file: Option<String>,
    /// Without the window, e.g. in tests.
    headless: bool,
    /// The address of the session host; without it the instance is the
    /// host (N-03).
    host: Option<String>,
    /// Searches for a host per mDNS; off with `--no-discovery`, e.g. in
    /// tests.
    discovery: bool,
}

fn run() -> Result<(), String> {
    let args = parse(env::args().skip(1))?;
    let library = match args.library.clone() {
        Some(library) => library,
        None => default_library().ok_or("no data directory, use --library <dir>")?,
    };
    let media = library.join("media");
    // The sound card plays and the announcement lasts as long as they live.
    let (role, _sound_card, discovery) = choose_role(&args, library)?;
    // A host serves the clients of other instances too (ADR 0010).
    let ip = match role {
        Role::Host(..) => Ipv4Addr::UNSPECIFIED,
        Role::Client(_) => Ipv4Addr::LOCALHOST,
    };
    let listener = TcpListener::bind((ip, args.control_port)).map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    if let Some(discovery) = &discovery {
        let status = match role {
            Role::Host(..) => Status::Host,
            Role::Client(_) => Status::Client,
        };
        let _ = discovery
            .announce(status, port)
            .inspect_err(|e| eprintln!("ERROR cannot announce the instance: {e}"));
    }
    println!(
        "Electrip {} control channel on {address}",
        env!("CARGO_PKG_VERSION")
    );
    // The gamepads stay on the thread that opens them.
    let server = thread::spawn(move || {
        // Without SDL the app still runs with the control channel.
        let mut gamepads = Gamepads::open()
            .inspect_err(|e| eprintln!("ERROR no gamepads: {e}"))
            .ok();
        let input = move || gamepads.as_mut().map(Gamepads::poll).unwrap_or_default();
        match role {
            Role::Host(host) => electrip_control::serve(listener, *host, input),
            Role::Client(host) => electrip_control::relay(listener, host, input),
        }
        .map_err(|e| e.to_string())
    });
    if !args.headless {
        match electrip_ui::run(address, media) {
            Ok(()) => return Ok(()),
            Err(e) => eprintln!("ERROR no window: {e}"),
        }
    }
    server.join().map_err(|_| "the control channel failed")?
}

/// The session host, or a client of the host at the address (N-03).
enum Role {
    Host(Box<Host>),
    Client(SocketAddr),
}

/// Without `--host` the instance searches for the host of its command
/// station, unless `--no-discovery`; it is host if there is none (N-03).
fn choose_role(
    args: &Args,
    library: PathBuf,
) -> Result<(Role, Option<MixerDeviceSink>, Option<Discovery>), String> {
    if let Some(host) = args.host.as_deref().and_then(reachable) {
        return Ok((Role::Client(host), None, None));
    }
    let (host, sound_card) = open_host(library, args.file.clone())?;
    let no_discovery = |e: &io::Error| eprintln!("ERROR no discovery: {e}");
    let discovery = if args.host.is_none() && args.discovery {
        let station = station_id(host.session().station());
        Discovery::start(station).inspect_err(no_discovery).ok()
    } else {
        None
    };
    let found = discovery
        .as_ref()
        .and_then(|d| d.find_host().inspect_err(no_discovery).ok()?);
    Ok(match found {
        Some(address) => (Role::Client(address), None, discovery),
        None => (Role::Host(Box::new(host)), sound_card, discovery),
    })
}

/// The address of the host; `None` if it cannot be reached, then the
/// instance is the host itself.
fn reachable(address: &str) -> Option<SocketAddr> {
    let reachable = address
        .to_socket_addrs()
        .and_then(|mut addresses| {
            addresses
                .find(|a| TcpStream::connect_timeout(a, HOST_TIMEOUT).is_ok())
                .ok_or_else(|| io::Error::other("no answer"))
        })
        .inspect_err(|e| eprintln!("ERROR cannot reach the host {address}: {e}"));
    reachable.ok()
}

/// The host on the library; it opens `file` instead of the first
/// configuration (B-24).
fn open_host(
    library: PathBuf,
    file: Option<String>,
) -> Result<(Host, Option<MixerDeviceSink>), String> {
    let connect = Box::new(|station: &Station| -> Result<Driver, _> {
        Ok(match station.kind {
            StationKind::Srcp => Box::new(SrcpStation::connect(
                &station.host,
                station.port,
                station.bus,
            )?),
            StationKind::Z21 => Box::new(Z21Station::connect(&station.host, station.port)?),
        })
    });
    // Without a sound card the sound models still run, silently.
    let (speaker, device) = match electrip_audio::sound_card() {
        Ok((speaker, device)) => (speaker, Some(device)),
        Err(e) => {
            eprintln!("ERROR no sound card: {e}");
            (Speaker::new(None), None)
        }
    };
    let mut host = Host::new(connect, Box::new(speaker), library).map_err(|e| e.to_string())?;
    if let Some(name) = file {
        let command = Command::OpenConfiguration { name };
        host.apply(command).map_err(|e| e.to_string())?;
    }
    Ok((host, device))
}

/// Reads the options; `--control-port 0` picks a free port.
fn parse(mut args: impl Iterator<Item = String>) -> Result<Args, String> {
    let mut parsed = Args {
        control_port: DEFAULT_CONTROL_PORT,
        library: None,
        file: None,
        headless: false,
        host: None,
        discovery: true,
    };
    while let Some(flag) = args.next() {
        if flag == "--headless" {
            parsed.headless = true;
            continue;
        }
        if flag == "--no-discovery" {
            parsed.discovery = false;
            continue;
        }
        let value = args.next().ok_or(USAGE)?;
        match flag.as_str() {
            "--control-port" => {
                parsed.control_port = value
                    .parse()
                    .map_err(|_| format!("invalid port: {value}"))?
            }
            "--library" => parsed.library = Some(value.into()),
            "-f" | "--file" => parsed.file = Some(value),
            "--host" => parsed.host = Some(value),
            _ => return Err(USAGE.into()),
        }
    }
    Ok(parsed)
}

/// `electrip` in the data directory of the user on each platform.
fn default_library() -> Option<PathBuf> {
    let home = || env::var_os("HOME").map(PathBuf::from);
    let data = if cfg!(windows) {
        env::var_os("APPDATA").map(PathBuf::from)
    } else if cfg!(target_os = "macos") {
        home().map(|h| h.join("Library/Application Support"))
    } else {
        env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .or_else(|| home().map(|h| h.join(".local/share")))
    };
    data.map(|d| d.join("electrip"))
}
