//! N-03: instances share one session host. Clients started with `--host`
//! forward their control channel to the host.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{App, Client};
use serde_json::{Value, json};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;
use std::time::{Duration, Instant};
use tempfile::TempDir;

/// The round trip of the network the requirement allows (Q-007).
const ROUND_TRIP: Duration = Duration::from_millis(20);

/// Starts a client of the host at `host`; it runs until dropped.
fn client_of(host: &str, library: &TempDir) -> App {
    App::start_in(library.path(), &["--host", host])
}

/// A proxy to `target` that delays each direction by half the round trip.
fn slow_network(target: &str) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap().to_string();
    let target = target.to_string();
    thread::spawn(move || {
        for client in listener.incoming() {
            let client = client.unwrap();
            let server = TcpStream::connect(&target).unwrap();
            delay(client.try_clone().unwrap(), server.try_clone().unwrap());
            delay(server, client);
        }
    });
    address
}

fn delay(mut from: TcpStream, mut to: TcpStream) {
    thread::spawn(move || {
        let mut buffer = [0; 65536];
        while let Ok(n @ 1..) = from.read(&mut buffer) {
            thread::sleep(ROUND_TRIP / 2);
            if to.write_all(&buffer[..n]).is_err() {
                break;
            }
        }
        let _ = to.shutdown(std::net::Shutdown::Both);
    });
}

/// Waits until the state of `client` satisfies `done`.
fn wait_for(client: &mut Client, done: impl Fn(&Value) -> bool) {
    while !done(&client.state) {
        client.expect_state();
    }
}

#[test]
fn a_change_in_one_instance_shows_in_all_others_within_300_ms() {
    let host = App::start();
    let network = slow_network(host.address());
    let (library_b, library_c) = (TempDir::new().unwrap(), TempDir::new().unwrap());
    let (b, c) = (
        client_of(&network, &library_b),
        client_of(&network, &library_c),
    );
    let mut at_host = host.connect();
    let mut at_b = b.connect();
    let mut at_c = c.connect();
    let has_loco = |state: &Value| state["locos"].as_array().unwrap().len() == 1;

    let start = Instant::now();
    at_b.command(json!({"command": "add_loco"})).unwrap();
    wait_for(&mut at_host, has_loco);
    wait_for(&mut at_c, has_loco);
    let took = start.elapsed();
    assert!(took < Duration::from_millis(300), "{took:?}");

    let renamed = |state: &Value| state["locos"][0]["name"] == "V 60";
    let start = Instant::now();
    at_host
        .command(json!({"command": "rename_loco", "loco": 1, "name": "V 60"}))
        .unwrap();
    wait_for(&mut at_b, renamed);
    wait_for(&mut at_c, renamed);
    let took = start.elapsed();
    assert!(took < Duration::from_millis(300), "{took:?}");
}

#[test]
fn the_devices_of_a_client_leave_with_it() {
    let host = App::start();
    let library = TempDir::new().unwrap();
    let client = client_of(host.address(), &library);
    let mut at_host = host.connect();
    let mut at_client = client.connect();
    let device = json!({"command": "add_device", "device": 7, "kind": "Gamepad"});
    at_client.command(device).unwrap();
    wait_for(&mut at_host, |state| state["devices"][0]["id"] == 7);

    drop(at_client);
    wait_for(&mut at_host, |state| state["devices"] == json!([]));
}

#[test]
fn an_unreachable_host_leaves_the_instance_on_its_own() {
    let unused = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = unused.local_addr().unwrap().to_string();
    drop(unused);
    let library = TempDir::new().unwrap();
    let app = client_of(&address, &library);
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    assert!(library.path().join("Electrip.json").exists());
}
