//! Electrip 2. The window is a client of the control channel on localhost
//! (N-08); without a display or with `--headless` the app runs without it.
//! The instance is the session host or a client of the host it finds per
//! mDNS or at `--host` (N-03).

use electrip_audio::{MixerDeviceSink, Speaker};
use electrip_control::{Discovery, Relay, Status, station_id};
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
    let mut args = parse(env::args().skip(1))?;
    let library = match args.library.take() {
        Some(library) => library,
        None => default_library().ok_or("no data directory, use --library <dir>")?,
    };
    let media = library.join("media");
    // The sound card plays as long as it lives.
    let (role, _sound_card, discovery) = choose_role(&args, library.clone())?;
    // A host serves the clients of other instances too (ADR 0010); a
    // client keeps the port if it becomes host.
    let listener =
        TcpListener::bind((Ipv4Addr::UNSPECIFIED, args.control_port)).map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let status = match role {
        Role::Host(..) => Status::Host,
        Role::Client(_) => Status::Client,
    };
    announce(discovery.as_ref(), status, port);
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
            Role::Client(host) => client(listener, host, input, discovery, library, args.file),
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

/// Relays to the host; when there is no host left, the instance becomes
/// host itself on a port of its own, and the relay passes its clients on
/// (N-03).
fn client(
    listener: TcpListener,
    host: SocketAddr,
    mut input: impl FnMut() -> Vec<Command>,
    discovery: Option<Discovery>,
    library: PathBuf,
    file: Option<String>,
) -> io::Result<()> {
    let port = listener.local_addr()?.port();
    let mut relay = Relay::start(listener, host);
    follow(&mut relay, host, &mut input, discovery.as_ref(), port);
    let (host, _sound_card) = take_over(&relay, library, file)?;
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0))?;
    relay.switch(listener.local_addr()?);
    announce(discovery.as_ref(), Status::Host, port);
    electrip_control::serve(listener, host, input)
}

fn announce(discovery: Option<&Discovery>, status: Status, port: u16) {
    if let Some(discovery) = discovery {
        let _ = discovery
            .announce(status, port)
            .inspect_err(|e| eprintln!("ERROR cannot announce the instance: {e}"));
    }
}

/// Relays to the host and, when it is gone, to the next host the discovery
/// finds; returns when there is none, so the instance becomes host (N-03).
fn follow(
    relay: &mut Relay,
    mut host: SocketAddr,
    mut input: impl FnMut() -> Vec<Command>,
    discovery: Option<&Discovery>,
    port: u16,
) {
    loop {
        if let Err(e) = relay.run(&mut input) {
            eprintln!("ERROR the host {host} is gone: {e}");
        }
        let Some(discovery) = discovery else { return };
        announce(Some(discovery), Status::Searching, port);
        let next = discovery
            .find_host(Some(host))
            .inspect_err(|e| eprintln!("ERROR no discovery: {e}"));
        match next.ok().flatten().filter(answers) {
            Some(next) => host = next,
            None => return,
        }
        relay.switch(host);
        announce(Some(discovery), Status::Client, port);
    }
}

/// The new host after the old one is gone: it reads back the state from
/// the command station and knows the input devices of the relay
/// (ADR 0010).
fn take_over(
    relay: &Relay,
    library: PathBuf,
    file: Option<String>,
) -> io::Result<(Host, Option<MixerDeviceSink>)> {
    let (mut host, sound_card) = open_host(library, file).map_err(io::Error::other)?;
    let _ = host
        .take_over()
        .inspect_err(|e| eprintln!("ERROR cannot take over the command station: {e}"));
    for command in relay.devices() {
        let _ = host.apply(command.clone());
    }
    Ok((host, sound_card))
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
        .and_then(|d| d.find_host(None).inspect_err(no_discovery).ok()?)
        // An announcement can outlive a host that crashed.
        .filter(answers);
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
                .find(answers)
                .ok_or_else(|| io::Error::other("no answer"))
        })
        .inspect_err(|e| eprintln!("ERROR cannot reach the host {address}: {e}"));
    reachable.ok()
}

fn answers(host: &SocketAddr) -> bool {
    TcpStream::connect_timeout(host, HOST_TIMEOUT).is_ok()
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
