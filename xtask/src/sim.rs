//! `cargo xtask sim up|down`: srcpd with a loopback bus (`sim/srcpd/`),
//! checked by the srcpd-loopback tests. srcpd runs directly where it is
//! installed, as in the devcontainer, which has no Docker; else in Docker.

use crate::{Result, root};
use std::io::{BufRead, BufReader};
use std::net::TcpStream;
use std::process::Command;
use std::thread::sleep;
use std::time::{Duration, Instant};

const NAME: &str = "electrip-srcpd";
const ADDR: &str = "127.0.0.1:4303";

pub fn sim(action: Option<&str>) -> Result {
    match action {
        Some("up") => up(),
        Some("down") => stop(native()),
        _ => Err("usage: cargo xtask sim <up | down>".into()),
    }
}

/// (Re)starts srcpd, then runs the srcpd-loopback tests.
fn up() -> Result {
    let native = native();
    stop(native)?;
    let dir = root().join("sim/srcpd");
    if native {
        run("srcpd", &["-f", &dir.join("srcpd.conf").to_string_lossy()])?;
    } else {
        run(
            "docker",
            &["build", "-q", "-t", NAME, &dir.to_string_lossy()],
        )?;
        let port = format!("{ADDR}:4303");
        run("docker", &["run", "-d", "--name", NAME, "-p", &port, NAME])?;
    }
    wait_for_srcpd()?;
    println!("ok    sim up (srcpd on {ADDR}, loopback bus 1)");
    loopback_tests()
}

fn stop(native: bool) -> Result {
    if !native {
        return run("docker", &["rm", "-f", NAME]);
    }
    // srcpd may linger after SIGTERM, so kill it. pkill fails when no srcpd
    // runs, which is fine.
    let _ = Command::new("pkill")
        .args(["-KILL", "-x", "srcpd"])
        .status();
    let deadline = Instant::now() + Duration::from_secs(10);
    while TcpStream::connect(ADDR).is_ok() {
        if Instant::now() > deadline {
            return Err("srcpd still running after pkill".into());
        }
        sleep(Duration::from_millis(100));
    }
    Ok(())
}

fn native() -> bool {
    Command::new("srcpd").arg("-v").output().is_ok()
}

fn run(program: &str, args: &[&str]) -> Result {
    let out = Command::new(program)
        .args(args)
        .output()
        .map_err(|e| format!("{program}: {e}"))?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        return Err(format!("{program} {}: {}", args.join(" "), err.trim()));
    }
    Ok(())
}

/// srcpd is ready when it greets. Until then, connections fail, or Docker's
/// port proxy accepts them but closes them at once.
fn wait_for_srcpd() -> Result {
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let mut greeting = String::new();
        if let Ok(stream) = TcpStream::connect(ADDR) {
            let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
            let _ = BufReader::new(stream).read_line(&mut greeting);
        }
        if greeting.starts_with("srcpd") {
            return Ok(());
        }
        if Instant::now() > deadline {
            return Err(format!("srcpd does not answer on {ADDR}"));
        }
        sleep(Duration::from_millis(200));
    }
}

/// The scenario tests of the srcpd driver and of the app over the control
/// channel (srcpd-loopback): all integration tests marked `#[ignore]`.
fn loopback_tests() -> Result {
    let args = [
        "test",
        "-p",
        "electrip-station-srcp",
        "-p",
        "electrip",
        "--tests",
        "--",
        "--ignored",
    ];
    crate::run_logged("srcpd-loopback", &args)
}
