//! Test helper for the control channel (N-08): starts the app on a free port
//! and talks to it. Other requirements cover their check `control-channel`
//! with it: `mod common;` in a test file under `crates/electrip/tests/`.

// Test code: unwrap and panic are allowed (AGENTS.md); not every test uses
// every helper.
#![allow(clippy::unwrap_used, clippy::panic, dead_code)]

pub mod changes;
pub mod diesel;
pub mod srcpd;

use electrip_core::station::{CommandStation, StationEvent};
use serde_json::{Value, json};
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpStream, UdpSocket};
use std::path::Path;
use std::process::{Child, ChildStdout, Command, Stdio};
use std::time::{Duration, Instant};
use tempfile::TempDir;

/// The running app; it is stopped when dropped.
pub struct App {
    child: Child,
    address: String,
    /// The library of [`App::start`], deleted when dropped.
    _library: Option<TempDir>,
}

impl App {
    /// Starts the app with an empty library.
    pub fn start() -> App {
        let library = TempDir::new().unwrap();
        let mut app = App::start_in(library.path(), &[]);
        app._library = Some(library);
        app
    }

    /// Starts the app with the library and further options; without
    /// discovery, so tests do not find each other.
    pub fn start_in(library: &Path, args: &[&str]) -> App {
        App::start_with(library, &[&["--no-discovery"], args].concat())
    }

    /// Starts the app with the library and the options.
    pub fn start_with(library: &Path, args: &[&str]) -> App {
        let mut child = Command::new(env!("CARGO_BIN_EXE_electrip"))
            .args(["--headless", "--control-port", "0", "--library"])
            .arg(library)
            .args(args)
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let address = read_address(child.stdout.take().unwrap());
        App {
            child,
            address,
            _library: None,
        }
    }

    /// The address of the control channel.
    pub fn address(&self) -> &str {
        &self.address
    }

    /// A new client, after the greeting; `state` holds the initial state.
    pub fn connect(&self) -> Client {
        self.try_connect().unwrap()
    }

    /// Like [`App::connect`]; `None` if the connection closes before the
    /// greeting.
    pub fn try_connect(&self) -> Option<Client> {
        let stream = TcpStream::connect(&self.address).ok()?;
        // A missing message fails the test instead of blocking it.
        stream
            .set_read_timeout(Some(Duration::from_secs(5)))
            .unwrap();
        let mut client = Client {
            reader: BufReader::new(stream.try_clone().unwrap()),
            writer: stream,
            hello: Value::Null,
            state: Value::Null,
        };
        let mut hello = String::new();
        client.reader.read_line(&mut hello).ok()?;
        client.hello = serde_json::from_str(&hello).ok()?;
        assert_eq!(client.hello["type"], "hello");
        client.expect_state();
        Some(client)
    }
}

impl Drop for App {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn read_address(stdout: ChildStdout) -> String {
    let mut line = String::new();
    BufReader::new(stdout).read_line(&mut line).unwrap();
    let (_, address) = line.trim().rsplit_once(" on ").unwrap();
    address.to_string()
}

pub struct Client {
    reader: BufReader<TcpStream>,
    writer: TcpStream,
    pub hello: Value,
    /// The last state received.
    pub state: Value,
}

impl Client {
    /// Sends a raw line and returns the reply; after a success the new
    /// state is read into `state`.
    /// States that arrive before the reply, e.g. while a loco accelerates,
    /// are read into `state` as well.
    pub fn send_line(&mut self, line: &str) -> Value {
        self.writer
            .write_all(format!("{line}\n").as_bytes())
            .unwrap();
        let mut reply = self.next();
        while reply["type"] == "state" {
            self.state = reply["state"].clone();
            reply = self.next();
        }
        assert_eq!(reply["type"], "reply", "{reply}");
        if reply["ok"] == true {
            self.expect_state();
        }
        reply
    }

    /// Sends a command; `Err` carries the error message of the reply.
    pub fn command(&mut self, command: Value) -> Result<(), String> {
        let reply = self.send_line(&command.to_string());
        match reply["error"].as_str() {
            None => Ok(()),
            Some(error) => Err(error.to_string()),
        }
    }

    /// Waits for the next state message, e.g. after another client's command.
    pub fn expect_state(&mut self) {
        let message = self.next();
        assert_eq!(message["type"], "state", "{message}");
        self.state = message["state"].clone();
    }

    /// Waits until `field` of loco 1 is `value`.
    pub fn wait_for_loco(&mut self, field: &str, value: Value) {
        while self.state["locos"][0][field] != value {
            self.expect_state();
        }
    }

    pub fn next(&mut self) -> Value {
        let mut line = String::new();
        self.reader.read_line(&mut line).unwrap();
        serde_json::from_str(&line).unwrap()
    }
}

/// Adds loco 1 that takes one second to accelerate and to brake.
pub fn add_quick_loco(client: &mut Client) {
    client.command(json!({"command": "add_loco"})).unwrap();
    for command in ["set_accel_duration", "set_brake_duration"] {
        client
            .command(json!({"command": command, "loco": 1, "seconds": 1}))
            .unwrap();
    }
}

/// Deflects the drive axis of loco 1.
pub fn set_axis(client: &mut Client, deflection: f64) {
    client
        .command(json!({"command": "set_axis", "loco": 1, "deflection": deflection}))
        .unwrap();
}

/// Waits until `station` reports an event that `matches`.
pub fn expect_event(station: &mut dyn CommandStation, matches: impl Fn(&StationEvent) -> bool) {
    let deadline = Instant::now() + Duration::from_secs(5);
    while Instant::now() < deadline {
        if station.events().iter().any(&matches) {
            return;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    panic!("ERROR the command station did not report the expected event");
}

/// Starts a Z21 simulator on a free port; it runs until the test ends.
pub fn z21_simulator() -> u16 {
    let socket = UdpSocket::bind("127.0.0.1:0").unwrap();
    let port = socket.local_addr().unwrap().port();
    std::thread::spawn(move || electrip_sim_z21::serve(socket));
    port
}
