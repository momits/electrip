//! B-13 with srcpd (`cargo xtask sim up`): with the driving sound on, srcpd
//! gets the first step > 0 only when the sound leading into the first
//! segment begins, and step 0 only when the sound leading out of it begins.
//! The app knows how long the sounds are, also without a sound card.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::diesel::{add_diesel, set_segment_sounds, toggle_sound};
use common::srcpd::{connect_to_srcpd, observer};
use common::{Client, set_axis};
use electrip_core::station::{CommandStation, StationEvent};
use electrip_station_srcp::SrcpStation;
use serde_json::json;
use std::time::{Duration, Instant};

const ADDRESS: u16 = 43;

/// The steps srcpd reported for the loco since the last call.
fn steps(observer: &mut SrcpStation) -> Vec<u8> {
    let events = observer.events().into_iter();
    events
        .filter_map(|event| match event {
            StationEvent::Loco { address, state } if address == ADDRESS => Some(state.step),
            _ => None,
        })
        .collect()
}

/// Seconds since `start` until srcpd reports a step that `matches`.
fn seconds_until(observer: &mut SrcpStation, start: Instant, matches: fn(u8) -> bool) -> f64 {
    while !steps(observer).into_iter().any(matches) {
        assert!(start.elapsed() < Duration::from_secs(5), "no such step");
        std::thread::sleep(Duration::from_millis(5));
    }
    start.elapsed().as_secs_f64()
}

fn wait_for(client: &mut Client, field: &str, value: serde_json::Value) {
    while client.state["locos"][0][field] != value {
        client.expect_state();
    }
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn srcpd_follows_the_driving_sound() {
    let app = common::App::start();
    let dir = tempfile::TempDir::new().unwrap();
    let mut client = connect_to_srcpd(&app);
    add_diesel(&mut client, dir.path());
    set_segment_sounds(&mut client, dir.path(), 0.5);
    client
        .command(json!({"command": "set_address", "loco": 1, "address": ADDRESS}))
        .unwrap();
    let mut observer = observer();
    toggle_sound(&mut client);
    wait_for(&mut client, "sound", json!("on"));

    // The idle sound plays and the next one waits: 2 · 0.3 s.
    let start = Instant::now();
    steps(&mut observer);
    set_axis(&mut client, 1.0);
    let seconds = seconds_until(&mut observer, start, |step| step > 0);
    assert!((0.55..1.0).contains(&seconds), "{seconds} s to start");

    // A load sound plays and the next one waits: 0.5 to 1 s.
    set_axis(&mut client, -1.0);
    wait_for(&mut client, "speed", json!(0.0));
    let start = Instant::now();
    assert!(!steps(&mut observer).contains(&0), "stopped too early");
    let seconds = seconds_until(&mut observer, start, |step| step == 0);
    assert!((0.45..1.2).contains(&seconds), "{seconds} s to stop");
}
