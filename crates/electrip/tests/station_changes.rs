//! N-03: the host takes over changes by another program at the command
//! station as the new starting point, but not the reports of what it sent
//! itself. Against the Z21 simulator; the tests marked `#[ignore]` need
//! srcpd (`cargo xtask sim up`).

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::srcpd::{connect_to_srcpd, observer};
use common::{App, Client, add_quick_loco, set_axis, z21_simulator};
use electrip_core::decoder::{Decoder, Protocol};
use electrip_core::station::{CommandStation, LocoState};
use electrip_station_z21::Z21Station;
use serde_json::json;

/// The app connected to the Z21 simulator and another program there.
fn on_z21() -> (App, Client, Z21Station) {
    let port = z21_simulator();
    let other = Z21Station::connect("127.0.0.1", port).unwrap();
    let app = App::start();
    let mut client = app.connect();
    let server = json!({"command": "set_server", "kind": "z21", "host": "127.0.0.1", "port": port, "bus": 0});
    client.command(server).unwrap();
    client.command(json!({"command": "connect"})).unwrap();
    (app, client, other)
}

/// Loco 1 of the app gets `address`; another program drives it back at
/// step 64 of 128, i.e. about half of Vmax.
fn takes_over_a_change_by_another_program(
    client: &mut Client,
    other: &mut dyn CommandStation,
    address: u16,
) {
    client.command(json!({"command": "add_loco"})).unwrap();
    let command = json!({"command": "set_address", "loco": 1, "address": address});
    client.command(command).unwrap();
    let decoder = Decoder::new(Protocol::DccShort, address, 128).unwrap();
    let state = LocoState {
        forward: false,
        step: 64,
        functions: 0,
    };
    other.set_loco(&decoder, &state).unwrap();
    client.wait_for_loco("forward", json!(false));
    let speed = client.state["locos"][0]["speed"].as_f64().unwrap();
    assert!((speed - 50.4).abs() < 0.1, "{speed}");
}

/// The reports of what the app sends while it accelerates do not set the
/// speed back.
fn accelerates_without_taking_its_own_reports(client: &mut Client, address: u16) {
    add_quick_loco(client);
    let command = json!({"command": "set_address", "loco": 1, "address": address});
    client.command(command).unwrap();
    set_axis(client, 1.0);
    let mut last = 0.0;
    while last < 100.0 {
        client.expect_state();
        let speed = client.state["locos"][0]["speed"].as_f64().unwrap();
        assert!(speed >= last, "ERROR the speed fell from {last} to {speed}");
        last = speed;
    }
    set_axis(client, 0.0);
    std::thread::sleep(std::time::Duration::from_millis(500));
    client.command(json!({"command": "add_loco"})).unwrap();
    assert_eq!(client.state["locos"][0]["speed"], 100.0);
}

#[test]
fn takes_over_a_change_on_the_z21() {
    let (_app, mut client, mut other) = on_z21();
    takes_over_a_change_by_another_program(&mut client, &mut other, 3);
}

/// A new host reads back what the locos do at the Z21.
#[test]
fn reads_back_the_locos_on_connecting_to_the_z21() {
    let port = z21_simulator();
    let mut other = Z21Station::connect("127.0.0.1", port).unwrap();
    let decoder = Decoder::new(Protocol::DccShort, 3, 128).unwrap();
    let state = LocoState {
        forward: false,
        step: 64,
        functions: 0,
    };
    other.set_loco(&decoder, &state).unwrap();
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    let command = json!({"command": "set_address", "loco": 1, "address": 3});
    client.command(command).unwrap();
    let server = json!({"command": "set_server", "kind": "z21", "host": "127.0.0.1", "port": port, "bus": 0});
    client.command(server).unwrap();
    client.command(json!({"command": "connect"})).unwrap();
    client.wait_for_loco("forward", json!(false));
    let speed = client.state["locos"][0]["speed"].as_f64().unwrap();
    assert!((speed - 50.4).abs() < 0.1, "{speed}");
}

#[test]
fn accelerates_on_the_z21_without_taking_its_own_reports() {
    let (_app, mut client, _) = on_z21();
    accelerates_without_taking_its_own_reports(&mut client, 3);
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn takes_over_a_change_on_srcpd() {
    let app = App::start();
    let mut client = connect_to_srcpd(&app);
    takes_over_a_change_by_another_program(&mut client, &mut observer(), 30);
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn accelerates_on_srcpd_without_taking_its_own_reports() {
    let app = App::start();
    let mut client = connect_to_srcpd(&app);
    accelerates_without_taking_its_own_reports(&mut client, 31);
}
