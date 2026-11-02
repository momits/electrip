//! B-05: acceleration and braking duration and volume of a loco are set
//! through the control channel, and every client sees them.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::App;
use serde_json::json;

#[test]
fn durations_and_volume_are_set() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    let loco = &client.state["locos"][0];
    assert_eq!(loco["accel_duration"], 11.5);
    assert_eq!(loco["brake_duration"], 8.5);
    assert_eq!(loco["volume"], 0.8);

    for command in [
        json!({"command": "set_accel_duration", "loco": 1, "seconds": 20}),
        json!({"command": "set_brake_duration", "loco": 1, "seconds": 4.5}),
        json!({"command": "set_volume", "loco": 1, "volume": 0.25}),
    ] {
        client.command(command).unwrap();
    }
    let loco = &client.state["locos"][0];
    assert_eq!(loco["accel_duration"], 20.0);
    assert_eq!(loco["brake_duration"], 4.5);
    assert_eq!(loco["volume"], 0.25);

    // Every client sees the result.
    assert_eq!(app.connect().state, client.state);
}

#[test]
fn values_out_of_range_name_the_reason() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    let before = client.state.clone();

    let brake = json!({"command": "set_brake_duration", "loco": 1, "seconds": 0});
    assert_eq!(
        client.command(brake),
        Err("the duration must be between 1 and 9999 s".into())
    );
    let volume = json!({"command": "set_volume", "loco": 1, "volume": 2});
    assert_eq!(
        client.command(volume),
        Err("the volume must be between 0 and 1".into())
    );
    assert_eq!(app.connect().state, before);
}
