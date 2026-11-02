//! B-10 over the control channel: the axis accelerates and brakes a loco,
//! the direction switch stops it and changes its direction. The test marked
//! `#[ignore]` checks with srcpd what the command station gets
//! (`cargo xtask sim up`).

// Test code: unwrap and panic are allowed (AGENTS.md).
#![allow(clippy::unwrap_used, clippy::panic)]

mod common;

use common::{App, Client};
use electrip_core::station::{CommandStation, LocoState, StationEvent};
use electrip_station_srcp::{DEFAULT_PORT, SrcpStation};
use serde_json::json;
use std::time::{Duration, Instant};

/// Adds loco 1 that takes one second to accelerate and to brake.
fn add_quick_loco(client: &mut Client) {
    client.command(json!({"command": "add_loco"})).unwrap();
    for command in ["set_accel_duration", "set_brake_duration"] {
        client
            .command(json!({"command": command, "loco": 1, "seconds": 1}))
            .unwrap();
    }
}

fn set_axis(client: &mut Client, deflection: f64) {
    client
        .command(json!({"command": "set_axis", "loco": 1, "deflection": deflection}))
        .unwrap();
}

/// Seconds until loco 1 reaches `speed`.
fn time_to(client: &mut Client, speed: f64) -> f64 {
    let start = Instant::now();
    while client.state["locos"][0]["speed"] != speed {
        client.expect_state();
    }
    start.elapsed().as_secs_f64()
}

#[test]
fn the_axis_accelerates_and_brakes() {
    let app = App::start();
    let mut client = app.connect();
    add_quick_loco(&mut client);
    set_axis(&mut client, 1.0);
    let seconds = time_to(&mut client, 100.0);
    assert!((0.9..1.5).contains(&seconds), "{seconds} s to accelerate");
    set_axis(&mut client, -1.0);
    let seconds = time_to(&mut client, 0.0);
    assert!((0.9..1.5).contains(&seconds), "{seconds} s to brake");
}

#[test]
fn reverse_stops_and_changes_the_direction() {
    let app = App::start();
    let mut client = app.connect();
    add_quick_loco(&mut client);
    set_axis(&mut client, 1.0);
    time_to(&mut client, 100.0);
    set_axis(&mut client, 0.0);
    client
        .command(json!({"command": "reverse", "loco": 1}))
        .unwrap();
    let loco = &client.state["locos"][0];
    assert_eq!(
        (&loco["speed"], &loco["forward"]),
        (&json!(0.0), &json!(false))
    );
}

/// Waits until `station` reports `state` for address 41.
fn expect_loco(station: &mut SrcpStation, state: LocoState) {
    let expected = StationEvent::Loco { address: 41, state };
    let deadline = Instant::now() + Duration::from_secs(5);
    while Instant::now() < deadline {
        if station.events().contains(&expected) {
            return;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    panic!("ERROR srcpd did not report {expected:?}");
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn srcpd_gets_the_speed_steps() {
    let app = App::start();
    let mut client = app.connect();
    add_quick_loco(&mut client);
    client
        .command(json!({"command": "set_address", "loco": 1, "address": 41}))
        .unwrap();
    client
        .command(
            json!({"command": "set_server", "host": "127.0.0.1", "port": DEFAULT_PORT, "bus": 1}),
        )
        .unwrap();
    client.command(json!({"command": "connect"})).unwrap();
    let mut observer = SrcpStation::connect("127.0.0.1", DEFAULT_PORT, 1).unwrap();

    set_axis(&mut client, 1.0);
    let full = LocoState {
        forward: true,
        step: 128,
        functions: 0,
    };
    expect_loco(&mut observer, full);
    set_axis(&mut client, 0.0);
    client
        .command(json!({"command": "reverse", "loco": 1}))
        .unwrap();
    expect_loco(&mut observer, LocoState::default());
}
