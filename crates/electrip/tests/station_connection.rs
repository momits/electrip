//! B-01 over the control channel: configure the SRCP server, connect,
//! notice a broken connection and connect again. A fake server stands in
//! for srcpd; the tests marked `#[ignore]` need srcpd (`cargo xtask sim up`).

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{App, Client};
use serde_json::json;
use std::io::{BufRead, BufReader, Write};
use std::net::{Shutdown, TcpListener, TcpStream};
use std::sync::{Arc, Mutex};
use std::thread;

/// Accepts SRCP sessions and confirms every line; `break_sessions` closes
/// the open ones as a broken connection would.
struct FakeServer {
    port: u16,
    sessions: Arc<Mutex<Vec<TcpStream>>>,
}

impl FakeServer {
    fn start() -> FakeServer {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let sessions = Arc::new(Mutex::new(Vec::new()));
        let open = Arc::clone(&sessions);
        thread::spawn(move || {
            for stream in listener.incoming() {
                let stream = stream.unwrap();
                open.lock().unwrap().push(stream.try_clone().unwrap());
                thread::spawn(move || confirm(stream));
            }
        });
        FakeServer { port, sessions }
    }

    fn break_sessions(&self) {
        for session in self.sessions.lock().unwrap().drain(..) {
            session.shutdown(Shutdown::Both).unwrap();
        }
    }
}

fn confirm(stream: TcpStream) {
    let mut writer = stream.try_clone().unwrap();
    writeln!(writer, "srcpd V2.1.7; SRCP 0.8.4").unwrap();
    for _ in BufReader::new(stream).lines().map_while(Result::ok) {
        if writeln!(writer, "1.0 200 OK").is_err() {
            return;
        }
    }
}

fn set_server(client: &mut Client, port: u16, bus: u16) {
    let server = json!({"command": "set_server", "host": "127.0.0.1", "port": port, "bus": bus});
    client.command(server).unwrap();
}

fn connect(client: &mut Client) -> Result<(), String> {
    client.command(json!({"command": "connect"}))
}

#[test]
fn the_server_is_configurable() {
    let app = App::start();
    let mut client = app.connect();
    assert_eq!(client.state["station"]["port"], 4303);
    set_server(&mut client, 4304, 2);
    let station = &app.connect().state["station"];
    assert_eq!(
        *station,
        json!({"host": "127.0.0.1", "port": 4304, "bus": 2, "connected": false})
    );
}

#[test]
fn connects_notices_a_broken_connection_and_reconnects() {
    let server = FakeServer::start();
    let app = App::start();
    let mut client = app.connect();
    set_server(&mut client, server.port, 1);
    connect(&mut client).unwrap();
    assert_eq!(client.state["station"]["connected"], true);
    let error = client.command(json!({"command": "set_server", "host": "x", "port": 1, "bus": 1}));
    assert_eq!(
        error,
        Err("disconnect from the command station first".into())
    );

    server.break_sessions();
    client.expect_state();
    assert_eq!(client.state["station"]["connected"], false);

    connect(&mut client).unwrap();
    assert_eq!(client.state["station"]["connected"], true);
    client.command(json!({"command": "disconnect"})).unwrap();
    assert_eq!(client.state["station"]["connected"], false);
}

#[test]
fn an_unreachable_server_is_reported() {
    let app = App::start();
    let mut client = app.connect();
    set_server(&mut client, 1, 1);
    let error = connect(&mut client).unwrap_err();
    assert!(
        error.starts_with("cannot reach the SRCP server 127.0.0.1:1"),
        "{error}"
    );
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn connects_to_srcpd() {
    let app = App::start();
    let mut client = app.connect();
    set_server(&mut client, 4303, 1);
    connect(&mut client).unwrap();
    assert_eq!(client.state["station"]["connected"], true);
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn a_missing_bus_of_srcpd_is_reported() {
    let app = App::start();
    let mut client = app.connect();
    set_server(&mut client, 4303, 7);
    let error = connect(&mut client).unwrap_err();
    assert!(
        error.starts_with("the SRCP server has no bus 7: "),
        "{error}"
    );
    assert_eq!(client.state["station"]["connected"], false);
}
