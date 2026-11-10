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

    let add = json!({"command": "add_loco"});
    shows_within_300_ms(&mut at_b, add, [&mut at_host, &mut at_c], has_loco);

    let renamed = |state: &Value| state["locos"][0]["name"] == "V 60";
    let rename = json!({"command": "rename_loco", "loco": 1, "name": "V 60"});
    shows_within_300_ms(&mut at_host, rename, [&mut at_b, &mut at_c], renamed);
}

/// The same with two configurations that both have a loco at address 3:
/// the client with a configuration of its own drives as a guest (Q-016).
#[test]
fn a_change_shows_in_other_configurations_within_300_ms() {
    let host = App::start();
    add_loco_at(&mut host.connect(), 3);
    let library_b = TempDir::new().unwrap();
    let alone = App::start_in(library_b.path(), &[]);
    let mut at_alone = alone.connect();
    add_loco_at(&mut at_alone, 3);
    at_alone
        .command(json!({"command": "rename_loco", "loco": 1, "name": "V 60"}))
        .unwrap();
    drop((at_alone, alone));
    let network = slow_network(host.address());
    let library_c = TempDir::new().unwrap();
    let (b, c) = (
        client_of(&network, &library_b),
        client_of(&network, &library_c),
    );
    let mut at_host = host.connect();
    let mut at_b = b.connect();
    let mut at_c = c.connect();
    assert_eq!(at_b.state["locos"][0]["name"], "V 60");
    assert_ne!(at_c.state["locos"][0]["name"], "V 60");
    let forward = |is: bool| move |state: &Value| state["locos"][0]["forward"] == is;

    // The locos of a guest get ids after those of the host.
    let reverse = json!({"command": "reverse", "loco": at_b.state["locos"][0]["id"]});
    let others = [&mut at_host, &mut at_c];
    shows_within_300_ms(&mut at_b, reverse, others, forward(false));

    let reverse = json!({"command": "reverse", "loco": 1});
    let others = [&mut at_host, &mut at_b];
    shows_within_300_ms(&mut at_c, reverse, others, forward(true));
}

/// Sends `command` at `from`; within 300 ms the states of the `others`
/// satisfy `done`.
fn shows_within_300_ms(
    from: &mut Client,
    command: Value,
    others: [&mut Client; 2],
    done: impl Fn(&Value) -> bool + Copy,
) {
    let start = Instant::now();
    from.command(command).unwrap();
    for other in others {
        wait_for(other, done);
    }
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

/// N-05: a client instance offers its output devices to the host, which
/// sends it the sounds of the locos that name it and measures the round
/// trip.
#[test]
fn a_client_is_an_audio_target_while_connected() {
    let host = App::start();
    let library = TempDir::new().unwrap();
    let client = client_of(host.address(), &library);
    let instance = std::fs::read_to_string(library.path().join("instance")).unwrap();
    let mut at_host = host.connect();
    wait_for(&mut at_host, |state| {
        state["audio_targets"][&instance].is_array()
    });
    // The host measures the round trip to it.
    wait_for(&mut at_host, |state| {
        state["audio_latency"][&instance].is_u64()
    });

    drop(client);
    wait_for(&mut at_host, |state| state["audio_targets"] == json!({}));
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
    connect_until(app, |state| state["station"]["connected"] == true)
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
    ask_to_join(&b, &a);

    let mut at_b = connect_until(&b, |state| state["locos"].as_array().unwrap().len() == 1);
    at_b.command(json!({"command": "add_loco"})).unwrap();
    wait_for(&mut at_a, |state| {
        state["locos"].as_array().unwrap().len() == 2
    });
}

/// A client joins the host entered in its window by itself; its old host
/// stays host.
#[test]
fn a_client_joins_the_host_at_the_address_entered() {
    let (a, b) = (App::start(), App::start());
    let library = TempDir::new().unwrap();
    let c = client_of(b.address(), &library);
    a.connect().command(json!({"command": "add_loco"})).unwrap();
    ask_to_join(&c, &a);

    connect_until(&c, |state| state["locos"].as_array().unwrap().len() == 1);
    assert_eq!(b.connect().state["locos"], json!([]));
}

/// Sends `join_host` with the address of `host` to `app`; the connection
/// closes after the reply, with no state.
fn ask_to_join(app: &App, host: &App) {
    let mut stream = TcpStream::connect(app.address()).unwrap();
    let join = json!({"command": "join_host", "address": host.address()});
    writeln!(stream, "{join}").unwrap();
    let mut messages = String::new();
    stream.read_to_string(&mut messages).unwrap();
    assert!(
        messages.ends_with("{\"ok\":true,\"type\":\"reply\"}\n"),
        "{messages}"
    );
}

/// Connects to `app` until its state satisfies `done`, e.g. once it
/// relays to another host.
fn connect_until(app: &App, done: impl Fn(&Value) -> bool) -> Client {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        match app.try_connect() {
            Some(client) if done(&client.state) => return client,
            _ => assert!(Instant::now() < deadline, "ERROR not as expected"),
        }
        thread::sleep(Duration::from_millis(100));
    }
}

/// Q-016: a client instance with a configuration of its own drives with
/// it as a guest of the host.
#[test]
fn a_client_drives_with_its_own_configuration() {
    let host = App::start();
    let library = TempDir::new().unwrap();
    let alone = App::start_in(library.path(), &[]);
    let mut at_alone = alone.connect();
    at_alone.command(json!({"command": "add_loco"})).unwrap();
    at_alone
        .command(json!({"command": "rename_loco", "loco": 1, "name": "V 60"}))
        .unwrap();
    drop((at_alone, alone));

    let client = client_of(host.address(), &library);
    let mut at_client = client.connect();
    assert_eq!(at_client.state["locos"][0]["name"], "V 60");
    assert_eq!(host.connect().state["locos"], json!([]));
    let error = "change this configuration on the instance that opened it";
    assert_eq!(
        at_client.command(json!({"command": "add_loco"})),
        Err(error.into())
    );
}
