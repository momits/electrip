//! A diesel loco with sound files of known length; the app knows how long
//! they are, also without a sound card.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

use super::{Client, add_quick_loco};
use serde_json::json;
use std::fs;
use std::path::Path;

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
pub fn add_diesel(client: &mut Client, dir: &Path) {
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

/// Gives the only segment of loco 1 sounds of `seconds` each.
pub fn set_segment_sounds(client: &mut Client, dir: &Path, seconds: f64) {
    for sound in ["accel", "load", "decel", "idle"] {
        let path = dir.join(format!("segment-{sound}.wav"));
        wav(&path, seconds);
        let command = json!({"command": "set_segment_sound", "loco": 1, "segment": 0, "sound": sound, "path": path});
        client.command(command).unwrap();
    }
}

pub fn toggle_sound(client: &mut Client) {
    client
        .command(json!({"command": "toggle_sound", "loco": 1}))
        .unwrap();
}
