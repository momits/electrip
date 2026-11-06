//! B-12 over the control channel: while a diesel engine starts and quits,
//! the speed stays locked, even with the axis at full deflection. The app
//! knows how long the sounds are, also without a sound card.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::diesel::{add_diesel, set_segment_sounds, toggle_sound};
use common::{App, Client, set_axis};
use serde_json::json;
use std::time::Instant;

/// Seconds since `start` until the sound of loco 1 is `sound`; the loco
/// stands meanwhile.
fn standing_until(client: &mut Client, sound: &str, start: Instant) -> f64 {
    while client.state["locos"][0]["sound"] != sound {
        assert_eq!(client.state["locos"][0]["speed"], 0.0);
        client.expect_state();
    }
    start.elapsed().as_secs_f64()
}

fn drives_off(client: &mut Client) {
    while client.state["locos"][0]["speed"] == 0.0 {
        client.expect_state();
    }
}

#[test]
fn the_speed_is_locked_while_the_engine_starts_and_quits() {
    let app = App::start();
    let dir = tempfile::TempDir::new().unwrap();
    let mut client = app.connect();
    add_diesel(&mut client, dir.path());
    // Without segment sounds the engine falls silent while driving.
    set_segment_sounds(&mut client, dir.path(), 0.1);

    let start = Instant::now();
    toggle_sound(&mut client);
    assert_eq!(client.state["locos"][0]["sound"], "starting");
    set_axis(&mut client, 1.0);
    let seconds = standing_until(&mut client, "on", start);
    assert!((0.55..1.5).contains(&seconds), "{seconds} s to start");
    drives_off(&mut client);

    set_axis(&mut client, -1.0);
    client.wait_for_loco("speed", json!(0.0));
    let start = Instant::now();
    toggle_sound(&mut client);
    assert_eq!(client.state["locos"][0]["sound"], "stopping");
    set_axis(&mut client, 1.0);
    let seconds = standing_until(&mut client, "off", start);
    assert!((0.55..2.0).contains(&seconds), "{seconds} s to quit");
    drives_off(&mut client);
}
