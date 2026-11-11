//! Electrip 2. The window is a client of the control channel on localhost
//! (N-08); without a display or with `--headless` the app runs without it.
//! The instance is the session host or a client of the host it finds per
//! mDNS or at `--host`, and changes its role when the hosts change (N-03).

use electrip_control::{Discovery, Relay, Status, station_id};
use electrip_core::host::{Driver, Host};
use electrip_core::media::LibrarySink;
use electrip_core::session::{Command, Station};
use electrip_core::station::StationKind;
use electrip_input::Gamepads;
use electrip_station_srcp::SrcpStation;
use electrip_station_z21::Z21Station;
use std::env;
use std::io;
use std::net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::Arc;
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender};
use std::thread::{self, JoinHandle};
use std::time::Duration;

/// How often a host checks whether to yield to another host (N-03).
const WATCH_INTERVAL: Duration = Duration::from_secs(2);

/// How often the instance merges its configurations with the ones other
/// instances share (N-04).
const SYNC_INTERVAL: Duration = Duration::from_secs(5);

const USAGE: &str = "usage: electrip [--headless] [--control-port <port>] [--library <dir>] [-f|--file <configuration>] [--host <address[:port]>] [--no-discovery]";

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
    let id = electrip_control::instance_id(&library).map_err(|e| e.to_string())?;
    let (role, discovery) = choose_role(&args, library.clone(), id)?;
    // A host serves the clients of other instances too (ADR 0010); a
    // client keeps the port if it becomes host.
    let listener =
        TcpListener::bind((Ipv4Addr::UNSPECIFIED, args.control_port)).map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    println!(
        "Electrip {} control channel on {address}",
        env!("CARGO_PKG_VERSION")
    );
    let discovery = discovery.map(Arc::new);
    if let Some(discovery) = discovery.clone() {
        thread::spawn(move || share(&discovery, address));
    }
    let window_library = library.clone();
    // The gamepads stay on the thread that opens them.
    let server = thread::spawn(move || {
        // Without SDL the app still runs with the control channel.
        let mut gamepads = Gamepads::open()
            .inspect_err(|e| eprintln!("ERROR no gamepads: {e}"))
            .ok();
        let input = move || gamepads.as_mut().map(Gamepads::poll).unwrap_or_default();
        session(listener, role, input, discovery, id, library, args.file).map_err(|e| e.to_string())
    });
    if !args.headless {
        match electrip_ui::run(address, window_library) {
            Ok(()) => return Ok(()),
            Err(e) => eprintln!("ERROR no window: {e}"),
        }
    }
    server.join().map_err(|_| "the control channel failed")?
}

/// The session host, or a client of the host at the address (N-03).
enum Role {
    Host {
        host: Box<Host>,
        /// Why the instance runs alone, if the discovery fails.
        alone: Option<String>,
    },
    Client(SocketAddr),
}

/// Plays the role and changes it until the control channel fails: a host
/// hands over to a host with a smaller id, a client becomes host when
/// there is no host left (N-03). The relay keeps the port of the control
/// channel and passes its clients on to the host of the moment, which may
/// be the instance itself.
fn session(
    listener: TcpListener,
    mut role: Role,
    mut input: impl FnMut() -> Vec<Command>,
    discovery: Option<Arc<Discovery>>,
    id: u64,
    library: PathBuf,
    file: Option<String>,
) -> io::Result<()> {
    let port = listener.local_addr()?.port();
    let bind = || TcpListener::bind((Ipv4Addr::LOCALHOST, 0));
    // The host listens on a port of its own behind the relay.
    let mut private = None;
    let (first, client) = match &role {
        Role::Host { .. } => (private.insert(bind()?).local_addr()?, false),
        Role::Client(host) => (*host, true),
    };
    // The instance plays the sounds of the locos that name it (N-05).
    let audio = Box::new(LibrarySink {
        sink: Box::new(electrip_audio::sound_card()),
        library: library.clone(),
    });
    let mut relay = Relay::new(listener, first, client, id, audio);
    loop {
        role = match role {
            Role::Host { host, alone } => {
                let serving = match private.take() {
                    Some(listener) => listener,
                    None => bind()?,
                };
                relay.switch(serving.local_addr()?, false);
                if let Some(discovery) = &discovery {
                    announce(discovery, Status::Host, port);
                }
                let handover = watch(discovery.clone());
                let input = || relay.track(input());
                let next = electrip_control::serve(serving, *host, id, input, alone, || {
                    handover.try_recv().ok()
                })?;
                eprintln!("ERROR this instance hands over to the host {next}");
                Role::Client(next)
            }
            Role::Client(host) => {
                relay.switch(host, true);
                if let Some(discovery) = &discovery {
                    announce(discovery, Status::Client, port);
                }
                let local = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
                let (stop, copying) = copy_configuration(local, library.clone());
                follow(&mut relay, host, &mut input, discovery.as_deref(), port);
                drop(stop);
                let name = copying.join().ok().flatten().or_else(|| file.clone());
                take_over(&relay, library.clone(), name)?
            }
        }
    }
}

/// Checks in the background whether the host is to yield to another host,
/// since an unreachable one would hold up the host (N-03).
fn watch(discovery: Option<Arc<Discovery>>) -> Receiver<SocketAddr> {
    let (sender, receiver) = mpsc::channel();
    if let Some(discovery) = discovery {
        thread::spawn(move || {
            loop {
                thread::sleep(WATCH_INTERVAL);
                if let Some(host) = discovery.smaller_host().filter(answers) {
                    let _ = sender.send(host);
                    return;
                }
            }
        });
    }
    receiver
}

/// Copies the open configuration of the host behind the relay at `local`
/// into the library now and every [`SYNC_INTERVAL`] while the instance is
/// client, so it drives with it when it becomes host (N-03). Stops when
/// the sender is dropped and returns the name of the copy.
fn copy_configuration(
    local: SocketAddr,
    library: PathBuf,
) -> (Sender<()>, JoinHandle<Option<String>>) {
    let (stop, stopped) = mpsc::channel();
    let copying = thread::spawn(move || {
        let mut name = None;
        loop {
            match electrip_control::take_configuration(local, &library) {
                Ok(taken) => name = Some(taken),
                Err(e) => eprintln!("ERROR cannot copy the configuration of the host: {e}"),
            }
            if stopped.recv_timeout(SYNC_INTERVAL) != Err(RecvTimeoutError::Timeout) {
                return name;
            }
        }
    });
    (stop, copying)
}

/// Merges the configurations of the instance at `local` with the ones
/// the other instances share, also without a host or a command station
/// in common (N-04).
fn share(discovery: &Discovery, local: SocketAddr) {
    loop {
        thread::sleep(SYNC_INTERVAL);
        for peer in discovery.instances() {
            let _ = electrip_control::sync(local, peer)
                .inspect_err(|e| eprintln!("ERROR cannot share configurations with {peer}: {e}"));
        }
    }
}

fn announce(discovery: &Discovery, status: Status, port: u16) {
    let _ = discovery
        .announce(status, port)
        .inspect_err(|e| eprintln!("ERROR cannot announce the instance: {e}"));
}

/// Relays to the host and, when it is gone, to the next host the discovery
/// finds or a client asks to join; returns when there is none, so the
/// instance becomes host (N-03).
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
        if let Some(next) = relay.joined() {
            eprintln!("ERROR this instance joins the host {next}");
            host = next;
            continue;
        }
        let Some(discovery) = discovery else { return };
        announce(discovery, Status::Searching, port);
        let Some(next) = discovery.find_host(Some(host)).filter(answers) else {
            return;
        };
        host = next;
        relay.switch(host, true);
        announce(discovery, Status::Client, port);
    }
}

/// The new host after the old one is gone: it opens the configuration
/// `name`, reads back the state from the command station and knows the
/// input devices of the relay (ADR 0010).
fn take_over(relay: &Relay, library: PathBuf, name: Option<String>) -> io::Result<Role> {
    let mut host = open_host(library, name).map_err(io::Error::other)?;
    let _ = host
        .take_over()
        .inspect_err(|e| eprintln!("ERROR cannot take over the command station: {e}"));
    for command in relay.devices() {
        let _ = host.apply(command.clone());
    }
    Ok(hosting(host, None))
}

fn hosting(host: Host, alone: Option<String>) -> Role {
    Role::Host {
        host: Box::new(host),
        alone,
    }
}

/// Without `--host` the instance searches for the host of its command
/// station, unless `--no-discovery`; it is host if there is none (N-03).
fn choose_role(
    args: &Args,
    library: PathBuf,
    id: u64,
) -> Result<(Role, Option<Discovery>), String> {
    if let Some(host) = args.host.as_deref().and_then(reachable) {
        return Ok((Role::Client(host), None));
    }
    let host = open_host(library, args.file.clone())?;
    if args.host.is_some() || !args.discovery {
        return Ok((hosting(host, None), None));
    }
    Ok(match search(host.session().station(), id) {
        Ok((discovery, Some(address))) => (Role::Client(address), Some(discovery)),
        Ok((discovery, None)) => (hosting(host, None), Some(discovery)),
        Err(e) => (hosting(host, Some(no_discovery(e))), None),
    })
}

/// Announces the instance and searches for the host of the station.
fn search(station: &Station, id: u64) -> io::Result<(Discovery, Option<SocketAddr>)> {
    let discovery = Discovery::start(station_id(station), id)?;
    // An announcement can outlive a host that crashed.
    let found = discovery.find_host(None).filter(answers);
    Ok((discovery, found))
}

/// Reports the error; the instance runs alone, and says why.
fn no_discovery(e: io::Error) -> String {
    eprintln!("ERROR no discovery: {e}");
    e.to_string()
}

/// The address of the host; `None` if it cannot be reached, then the
/// instance is the host itself.
fn reachable(address: &str) -> Option<SocketAddr> {
    let found = electrip_control::find_host(address)
        .inspect_err(|e| eprintln!("ERROR cannot reach the host {address}: {e}"));
    found.ok().map(|(host, _)| host)
}

fn answers(host: &SocketAddr) -> bool {
    TcpStream::connect_timeout(host, electrip_control::HOST_TIMEOUT).is_ok()
}

/// The host on the library; it opens `file` instead of the first
/// configuration (B-24).
fn open_host(library: PathBuf, file: Option<String>) -> Result<Host, String> {
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
    let speaker = Box::new(electrip_audio::sound_card());
    let mut host = Host::new(connect, speaker, library).map_err(|e| e.to_string())?;
    if let Some(name) = file {
        let command = Command::OpenConfiguration { name };
        host.apply(command).map_err(|e| e.to_string())?;
    }
    Ok(host)
}

/// Reads the options; `--control-port 0` picks a free port.
fn parse(mut args: impl Iterator<Item = String>) -> Result<Args, String> {
    let mut parsed = Args {
        control_port: electrip_control::DEFAULT_PORT,
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
