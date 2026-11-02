//! Test helper for the control channel (N-08): starts the app on a free port
//! and talks to it. Other requirements cover their check `control-channel`
//! with it: `mod common;` in a test file under `crates/electrip/tests/`.

// Test code: unwrap is allowed (AGENTS.md); not every test uses every helper.
#![allow(clippy::unwrap_used, dead_code)]

use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;
use std::process::{Child, ChildStdout, Command, Stdio};

/// The running app; it is stopped when dropped.
pub struct App {
    child: Child,
    address: String,
}

impl App {
    pub fn start() -> App {
        let mut child = Command::new(env!("CARGO_BIN_EXE_electrip"))
            .args(["--control-port", "0"])
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let address = read_address(child.stdout.take().unwrap());
        App { child, address }
    }

    /// A new client, after the greeting; `state` holds the initial state.
    pub fn connect(&self) -> Client {
        let stream = TcpStream::connect(&self.address).unwrap();
        let mut client = Client {
            reader: BufReader::new(stream.try_clone().unwrap()),
            writer: stream,
            state: Value::Null,
        };
        assert_eq!(client.next()["type"], "hello");
        client.expect_state();
        client
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
    /// The last state received.
    pub state: Value,
}

impl Client {
    /// Sends a raw line and returns the reply; after a success the new
    /// state is read into `state`.
    pub fn send_line(&mut self, line: &str) -> Value {
        writeln!(self.writer, "{line}").unwrap();
        let reply = self.next();
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

    pub fn next(&mut self) -> Value {
        let mut line = String::new();
        self.reader.read_line(&mut line).unwrap();
        serde_json::from_str(&line).unwrap()
    }
}
