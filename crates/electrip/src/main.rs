//! Electrip 2. Without a user interface yet, the app runs headless and is
//! operated through the control channel on localhost (N-08).

use electrip_core::host::{Driver, Host};
use electrip_core::session::{Command, Station};
use electrip_input::Gamepads;
use electrip_station_srcp::SrcpStation;
use std::env;
use std::net::{Ipv4Addr, TcpListener};
use std::path::PathBuf;
use std::process::ExitCode;

const DEFAULT_CONTROL_PORT: u16 = 4711;

const USAGE: &str =
    "usage: electrip [--control-port <port>] [--library <dir>] [-f|--file <configuration>]";

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
}

fn run() -> Result<(), String> {
    let args = parse(env::args().skip(1))?;
    let library = match args.library {
        Some(library) => library,
        None => default_library().ok_or("no data directory, use --library <dir>")?,
    };
    let connect = Box::new(|station: &Station| {
        let driver = SrcpStation::connect(&station.host, station.port, station.bus)?;
        Ok(Box::new(driver) as Driver)
    });
    let mut host = Host::new(connect, library).map_err(|e| e.to_string())?;
    if let Some(name) = args.file {
        let command = Command::OpenConfiguration { name };
        host.apply(command).map_err(|e| e.to_string())?;
    }
    let listener =
        TcpListener::bind((Ipv4Addr::LOCALHOST, args.control_port)).map_err(|e| e.to_string())?;
    let address = listener.local_addr().map_err(|e| e.to_string())?;
    println!(
        "Electrip {} control channel on {address}",
        env!("CARGO_PKG_VERSION")
    );
    // Without SDL the app still runs with the control channel.
    let mut gamepads = Gamepads::open()
        .inspect_err(|e| eprintln!("ERROR no gamepads: {e}"))
        .ok();
    let input = move || gamepads.as_mut().map(Gamepads::poll).unwrap_or_default();
    electrip_control::serve(listener, host, input).map_err(|e| e.to_string())
}

/// Reads the options; `--control-port 0` picks a free port.
fn parse(mut args: impl Iterator<Item = String>) -> Result<Args, String> {
    let mut parsed = Args {
        control_port: DEFAULT_CONTROL_PORT,
        library: None,
        file: None,
    };
    while let Some(flag) = args.next() {
        let value = args.next().ok_or(USAGE)?;
        match flag.as_str() {
            "--control-port" => {
                parsed.control_port = value
                    .parse()
                    .map_err(|_| format!("invalid port: {value}"))?
            }
            "--library" => parsed.library = Some(value.into()),
            "-f" | "--file" => parsed.file = Some(value),
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
