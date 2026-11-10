//! N-03: instances share one session host. Clients started with `--host`
//! forward their control channel to the host.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::changes::{add_loco_at, connect_to_z21, drive_back_at_half, expect_back_at_half};
use common::{App, Client, z21_simulator};
use electrip_station_z21::Z21Station;
use serde_json::{Value, json};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream, UdpSocket};
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
    to.set_nodelay(true).unwrap();
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
    // A freed port could go to an app of another test; nothing listens on
    // the privileged port 1.
    let library = TempDir::new().unwrap();
    let app = client_of("127.0.0.1:1", &library);
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    assert!(library.path().join("Electrip.json").exists());
}

/// Host-Ausfall: a client becomes host and reads back the locos from the
/// command station.
#[test]
fn a_client_becomes_host_when_the_host_is_gone() {
    let port = z21_simulator();
    // Until Q-016 the client has the same configuration as the host.
    let library = TempDir::new().unwrap();
    let configure = |client: &mut Client| {
        add_loco_at(client, 3);
        connect_to_z21(client, port);
    };
    configure(&mut App::start_in(library.path(), &[]).connect());
    let host = App::start();
    configure(&mut host.connect());
    let client = client_of(host.address(), &library);
    drive_back_at_half(&mut Z21Station::connect("127.0.0.1", port).unwrap(), 3);
    expect_back_at_half(&mut client.connect());

    drop(host);
    let mut at_client = connect_when_host(&client);
    assert_eq!(at_client.state["station"]["connected"], true);
    expect_back_at_half(&mut at_client);
}

/// Connects to `app` once it is host itself; before that its relay closes
/// each connection to the host that is gone.
fn connect_when_host(app: &App) -> Client {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        match app.try_connect() {
            Some(client) if client.state["station"]["connected"] == true => return client,
            _ => assert!(Instant::now() < deadline, "ERROR no new host"),
        }
        thread::sleep(Duration::from_millis(100));
    }
}

/// Without access to the local network (as in the container, where
/// multicast is not permitted) the instance runs alone and tells its
/// clients why; with access it says nothing.
#[test]
fn an_instance_without_network_says_it_runs_alone() {
    let library = TempDir::new().unwrap();
    let app = App::start_with(library.path(), &[]);
    let client = app.connect();
    let multicast = UdpSocket::bind("0.0.0.0:0")
        .and_then(|s| s.send_to(&[0; 12], "224.0.0.251:5353"))
        .is_ok();
    let alone = client.hello["alone"].as_str();
    assert_eq!(alone.is_none(), multicast, "{}", client.hello);
    if let Some(reason) = alone {
        assert!(
            reason.starts_with("no access to the local network"),
            "{reason}"
        );
    }
}

/// Rückfall ohne mDNS: a host joins the host whose address the user
/// enters in the window; it is no host of its own afterwards.
#[test]
fn a_host_joins_the_host_at_the_address_entered() {
    let (a, b) = (App::start(), App::start());
    let mut at_a = a.connect();
    at_a.command(json!({"command": "add_loco"})).unwrap();
    // The connection closes after the reply, with no state.
    let mut at_b = TcpStream::connect(b.address()).unwrap();
    let join = json!({"command": "join_host", "address": a.address()});
    writeln!(at_b, "{join}").unwrap();
    let mut messages = String::new();
    at_b.read_to_string(&mut messages).unwrap();
    assert!(
        messages.ends_with("{\"ok\":true,\"type\":\"reply\"}\n"),
        "{messages}"
    );

    let mut at_b = connect_until(&b, |state| state["locos"].as_array().unwrap().len() == 1);
    at_b.command(json!({"command": "add_loco"})).unwrap();
    wait_for(&mut at_a, |state| {
        state["locos"].as_array().unwrap().len() == 2
    });
}

/// Connects to `app` until its state satisfies `done`, e.g. once it
/// relays to another host.
fn connect_until(app: &App, done: impl Fn(&Value) -> bool) -> Client {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        match app.try_connect() {
            Some(client) if done(&client.state) => return client,
            _ => assert!(Instant::now() < deadline, "ERROR no other host"),
        }
        thread::sleep(Duration::from_millis(100));
    }
}
