//! N-07 and B-07 over the control channel: logical actions switch the
//! decoder functions each loco maps them to. The test marked `#[ignore]`
//! checks with srcpd that the functions arrive (`cargo xtask sim up`).

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::expect_event;
use common::srcpd::{connect_to_srcpd, observer};
use common::{App, Client};
use electrip_core::station::StationEvent;
use serde_json::json;
use std::time::Duration;

/// Adds two locos, the action "Licht" (1) and maps it to F0 at loco 1 and
/// to F4 at loco 2.
fn add_light(client: &mut Client) {
    for command in [
        json!({"command": "add_loco"}),
        json!({"command": "add_loco"}),
        json!({"command": "add_action", "name": "Licht"}),
        json!({"command": "add_function", "loco": 1, "function": {"action": 1, "number": 0, "name": "Licht"}}),
        json!({"command": "add_function", "loco": 2, "function": {"action": 1, "number": 4, "name": "Licht", "mode": "push"}}),
    ] {
        client.command(command).unwrap();
    }
}

fn trigger(client: &mut Client, loco: u32, pressed: bool) {
    client
        .command(
            json!({"command": "trigger_action", "loco": loco, "action": 1, "pressed": pressed}),
        )
        .unwrap();
}

fn is_on(client: &Client, loco: usize) -> bool {
    client.state["locos"][loco]["functions"][0]["on"] == true
}

#[test]
fn an_action_switches_the_function_of_the_given_loco() {
    let app = App::start();
    let mut client = app.connect();
    add_light(&mut client);
    assert_eq!(client.state["actions"], json!([{"id": 1, "name": "Licht"}]));

    trigger(&mut client, 1, true);
    trigger(&mut client, 1, false);
    assert!(is_on(&client, 0));
    assert!(!is_on(&client, 1));

    trigger(&mut client, 2, true);
    assert!(is_on(&client, 1));
    trigger(&mut client, 2, false);
    assert!(!is_on(&client, 1));
}

#[test]
fn removing_an_action_removes_its_functions() {
    let app = App::start();
    let mut client = app.connect();
    add_light(&mut client);
    client
        .command(json!({"command": "remove_action", "action": 1}))
        .unwrap();
    assert_eq!(client.state["actions"], json!([]));
    assert_eq!(client.state["locos"][0]["functions"], json!([]));
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn srcpd_gets_the_functions() {
    let app = App::start();
    let mut client = connect_to_srcpd(&app);
    add_light(&mut client);
    for (loco, address) in [(1, 43), (2, 44)] {
        client
            .command(json!({"command": "set_address", "loco": loco, "address": address}))
            .unwrap();
    }
    let mut observer = observer();
    // The host sends a loco only after a change it sees in a poll (50 ms).
    std::thread::sleep(Duration::from_millis(200));
    let has_function = |e: &StationEvent, address, number| matches!(e, StationEvent::Loco { address: a, state } if *a == address && state.function(number));
    // One loco after the other: `expect_event` drops the other events.
    trigger(&mut client, 1, true);
    expect_event(&mut observer, |e| has_function(e, 43, 0));
    trigger(&mut client, 2, true);
    expect_event(&mut observer, |e| has_function(e, 44, 4));
}
