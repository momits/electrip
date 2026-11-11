//! B-10 over the control channel: the axis accelerates and brakes a loco,
//! the direction switch stops it and changes its direction. B-24: the mouse
//! sets the speed at once. The test marked
//! `#[ignore]` checks with srcpd what the command station gets
//! (`cargo xtask sim up`).

// Test code: unwrap and panic are allowed (AGENTS.md).
#![allow(clippy::unwrap_used, clippy::panic)]

mod common;

use common::expect_event;
use common::srcpd::{connect_to_srcpd, observer};
use common::{App, Client, add_quick_loco, set_axis};
use electrip_core::station::{LocoState, StationEvent};
use electrip_station_srcp::SrcpStation;
use serde_json::json;
use std::time::Instant;

/// Seconds until loco 1 reaches `speed`.
fn time_to(client: &mut Client, speed: f64) -> f64 {
    let start = Instant::now();
    client.wait_for_loco("speed", json!(speed));
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

#[test]
fn the_mouse_sets_the_speed() {
    let app = App::start();
    let mut client = app.connect();
    add_quick_loco(&mut client);
    client
        .command(json!({"command": "set_speed", "loco": 1, "speed": 40.0}))
        .unwrap();
    assert_eq!(client.state["locos"][0]["speed"], json!(40.0));
}

/// Waits until `station` reports `state` for address 41.
fn expect_loco(station: &mut SrcpStation, state: LocoState) {
    let expected = StationEvent::Loco { address: 41, state };
    expect_event(station, |e| *e == expected);
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn srcpd_gets_the_speed_steps() {
    let app = App::start();
    let mut client = connect_to_srcpd(&app);
    add_quick_loco(&mut client);
    client
        .command(json!({"command": "set_address", "loco": 1, "address": 41}))
        .unwrap();
    let mut observer = observer();

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
