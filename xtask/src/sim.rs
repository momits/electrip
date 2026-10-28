//! `cargo xtask sim up|down`: srcpd with a loopback bus in Docker
//! (`sim/srcpd/`), checked by a smoke test over SRCP.

use crate::{Result, root};
use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;
use std::process::Command;
use std::thread::sleep;
use std::time::{Duration, Instant};

const NAME: &str = "electrip-srcpd";
const ADDR: &str = "127.0.0.1:4303";

pub fn sim(action: Option<&str>) -> Result {
    match action {
        Some("up") => up(),
        Some("down") => docker(&["rm", "-f", NAME]),
        _ => Err("usage: cargo xtask sim <up | down>".into()),
    }
}

/// Builds and (re)starts the container, then runs the smoke test.
fn up() -> Result {
    let dir = root().join("sim/srcpd");
    docker(&["build", "-q", "-t", NAME, &dir.to_string_lossy()])?;
    docker(&["rm", "-f", NAME])?;
    let port = format!("{ADDR}:4303");
    docker(&["run", "-d", "--name", NAME, "-p", &port, NAME])?;
    smoke_test().map_err(|e| format!("smoke test: {e}"))?;
    println!("ok    sim up (srcpd on {ADDR}, loopback bus 1)");
    Ok(())
}

fn docker(args: &[&str]) -> Result {
    let out = Command::new("docker")
        .args(args)
        .output()
        .map_err(|e| format!("docker: {e}"))?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        return Err(format!("docker {}: {}", args.join(" "), err.trim()));
    }
    Ok(())
}

/// An INFO session must report the loco speed that a COMMAND session sets.
fn smoke_test() -> Result {
    let mut info = Session::connect("INFO")?;
    let mut command = Session::connect("COMMAND")?;
    command.request("INIT 1 GL 3 N 1 128 5")?;
    command.request("SET 1 GL 3 1 20 128 1 0 0 0 0")?;
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let line = info.read_line()?;
        if line.contains(" 100 INFO 1 GL 3 1 20 128 ") {
            return Ok(());
        }
        if Instant::now() > deadline {
            return Err(format!("no INFO for loco 3, last line '{line}'"));
        }
    }
}

struct Session(BufReader<TcpStream>);

impl Session {
    /// Retries while srcpd starts up: until then, Docker's port proxy accepts
    /// connections but closes them at once.
    fn connect(mode: &str) -> Result<Self> {
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            match Self::try_connect(mode) {
                Err(e) if Instant::now() > deadline => return Err(e),
                Err(_) => sleep(Duration::from_millis(200)),
                ok => return ok,
            }
        }
    }

    fn try_connect(mode: &str) -> Result<Self> {
        let stream = TcpStream::connect(ADDR).map_err(|e| e.to_string())?;
        let timeout = Some(Duration::from_secs(5));
        stream
            .set_read_timeout(timeout)
            .map_err(|e| e.to_string())?;
        let mut session = Session(BufReader::new(stream));
        let greeting = session.read_line()?;
        if !greeting.starts_with("srcpd") {
            return Err(format!("unexpected greeting '{greeting}'"));
        }
        session.request(&format!("SET CONNECTIONMODE SRCP {mode}"))?;
        session.request("GO")?;
        Ok(session)
    }

    /// Sends one command and expects a 2xx reply.
    fn request(&mut self, command: &str) -> Result {
        writeln!(self.0.get_mut(), "{command}").map_err(|e| e.to_string())?;
        let reply = self.read_line()?;
        match reply.split_whitespace().nth(1) {
            Some(code) if code.starts_with('2') => Ok(()),
            _ => Err(format!("'{command}' got '{reply}'")),
        }
    }

    fn read_line(&mut self) -> Result<String> {
        let mut line = String::new();
        match self.0.read_line(&mut line) {
            Ok(0) => Err("srcpd closed the connection".into()),
            Ok(_) => Ok(line.trim_end().to_string()),
            Err(e) => Err(format!("no reply from srcpd: {e}")),
        }
    }
}
