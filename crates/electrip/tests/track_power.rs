//! B-23 over the control channel: the emergency stop of the layout toggles
//! the track power, the loco emergency stop stops one loco. The tests marked
//! `#[ignore]` check with srcpd what the command station gets and that a
//! second instance sees the track power (`cargo xtask sim up`).

// Test code: unwrap and panic are allowed (AGENTS.md).
#![allow(clippy::unwrap_used, clippy::panic)]

mod common;

use common::expect_event;
use common::srcpd::{connect_to_srcpd, observer};
use common::{App, Client};
use electrip_core::station::StationEvent;
use serde_json::{Value, json};

#[test]
fn the_track_power_toggles_only_while_connected() {
    let app = App::start();
    let mut client = app.connect();
    let error = client.command(json!({"command": "toggle_power"}));
    assert_eq!(error, Err("connect to the command station first".into()));
}

#[test]
fn power_on_start_can_be_switched_off() {
    let app = App::start();
    let mut client = app.connect();
    assert_eq!(client.state["station"]["power_on_start"], true);
    client
        .command(json!({"command": "set_power_on_start", "on": false}))
        .unwrap();
    assert_eq!(client.state["station"]["power_on_start"], false);
}

/// Waits until the client gets a state with the track power `on`.
fn expect_track_power(client: &mut Client, on: bool) {
    while client.state["station"]["track_power"] != Value::Bool(on) {
        client.expect_state();
    }
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn the_track_power_toggles_and_reaches_other_instances() {
    let (app, other_app) = (App::start(), App::start());
    let mut observer = observer();
    let mut client = connect_to_srcpd(&app);
    expect_event(&mut observer, |e| *e == StationEvent::Power(true));
    let mut other = connect_to_srcpd(&other_app);
    assert_eq!(other.state["station"]["track_power"], true);

    client.command(json!({"command": "toggle_power"})).unwrap();
    assert_eq!(client.state["station"]["track_power"], false);
    expect_event(&mut observer, |e| *e == StationEvent::Power(false));
    expect_track_power(&mut other, false);

    other.command(json!({"command": "toggle_power"})).unwrap();
    expect_track_power(&mut client, true);
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn srcpd_gets_the_loco_emergency_stop() {
    let app = App::start();
    let mut client = connect_to_srcpd(&app);
    client.command(json!({"command": "add_loco"})).unwrap();
    for command in [
        json!({"command": "set_address", "loco": 1, "address": 42}),
        json!({"command": "set_accel_duration", "loco": 1, "seconds": 1}),
        json!({"command": "set_axis", "loco": 1, "deflection": 1}),
    ] {
        client.command(command).unwrap();
    }
    let mut observer = observer();
    let is_loco = |e: &StationEvent, step| matches!(e, StationEvent::Loco { address: 42, state } if state.step == step);
    expect_event(&mut observer, |e| is_loco(e, 128));

    client
        .command(json!({"command": "emergency_stop", "loco": 1}))
        .unwrap();
    assert_eq!(client.state["locos"][0]["speed"], 0.0);
    assert_eq!(client.state["station"]["track_power"], true);
    expect_event(&mut observer, |e| is_loco(e, 0));
}
