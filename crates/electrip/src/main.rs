//! Electrip 2. Without a user interface yet, the app runs headless and is
//! operated through the control channel on localhost (N-08).

use std::env;
use std::net::{Ipv4Addr, TcpListener};
use std::process::ExitCode;

const DEFAULT_CONTROL_PORT: u16 = 4711;

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("ERROR {e}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let port = control_port(env::args().skip(1).collect())?;
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, port)).map_err(|e| e.to_string())?;
    let address = listener.local_addr().map_err(|e| e.to_string())?;
    println!(
        "Electrip {} control channel on {address}",
        env!("CARGO_PKG_VERSION")
    );
    electrip_control::serve(listener).map_err(|e| e.to_string())
}

/// Reads `--control-port <port>`; port 0 picks a free port.
fn control_port(args: Vec<String>) -> Result<u16, String> {
    match args.as_slice() {
        [] => Ok(DEFAULT_CONTROL_PORT),
        [flag, port] if flag == "--control-port" => {
            port.parse().map_err(|_| format!("invalid port: {port}"))
        }
        _ => Err("usage: electrip [--control-port <port>]".into()),
    }
}
