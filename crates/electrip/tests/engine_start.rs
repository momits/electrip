//! B-12 over the control channel: while a diesel engine starts and quits,
//! the speed stays locked, even with the axis at full deflection. The app
//! knows how long the sounds are, also without a sound card.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{App, Client, add_quick_loco, set_axis};
use serde_json::json;
use std::fs;
use std::path::Path;
use std::time::Instant;

const RATE: u32 = 8000;

/// Writes a silent 16 bit mono WAV file of `seconds`.
fn wav(path: &Path, seconds: f64) {
    let data = (f64::from(RATE) * seconds) as u32 * 2;
    let mut bytes = b"RIFF".to_vec();
    bytes.extend((36 + data).to_le_bytes());
    bytes.extend(b"WAVEfmt ");
    bytes.extend(16u32.to_le_bytes());
    bytes.extend(1u16.to_le_bytes());
    bytes.extend(1u16.to_le_bytes());
    bytes.extend(RATE.to_le_bytes());
    bytes.extend((RATE * 2).to_le_bytes());
    bytes.extend(2u16.to_le_bytes());
    bytes.extend(16u16.to_le_bytes());
    bytes.extend(b"data");
    bytes.extend(data.to_le_bytes());
    bytes.resize(bytes.len() + data as usize, 0);
    fs::write(path, bytes).unwrap();
}

/// Adds loco 1 as in [`add_quick_loco`] with a diesel engine whose start
/// and quit sounds last 0.6 s and whose idle sound lasts 0.3 s.
fn add_diesel(client: &mut Client, dir: &Path) {
    add_quick_loco(client);
    client
        .command(json!({"command": "set_engine", "loco": 1, "engine": "diesel"}))
        .unwrap();
    for (sound, seconds) in [("start", 0.6), ("idle", 0.3), ("quit", 0.6)] {
        let path = dir.join(format!("{sound}.wav"));
        wav(&path, seconds);
        let command =
            json!({"command": "set_engine_sound", "loco": 1, "sound": sound, "path": path});
        client.command(command).unwrap();
    }
}

fn toggle_sound(client: &mut Client) {
    client
        .command(json!({"command": "toggle_sound", "loco": 1}))
        .unwrap();
}

/// Seconds until the sound of loco 1 is `sound`; the loco stands meanwhile.
fn standing_until(client: &mut Client, sound: &str) -> f64 {
    let start = Instant::now();
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

    toggle_sound(&mut client);
    assert_eq!(client.state["locos"][0]["sound"], "starting");
    set_axis(&mut client, 1.0);
    let seconds = standing_until(&mut client, "on");
    assert!((0.5..1.0).contains(&seconds), "{seconds} s to start");
    drives_off(&mut client);

    set_axis(&mut client, -1.0);
    while client.state["locos"][0]["speed"] != 0.0 {
        client.expect_state();
    }
    toggle_sound(&mut client);
    assert_eq!(client.state["locos"][0]["sound"], "stopping");
    set_axis(&mut client, 1.0);
    let seconds = standing_until(&mut client, "off");
    assert!((0.5..1.4).contains(&seconds), "{seconds} s to quit");
    drives_off(&mut client);
}
