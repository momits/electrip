//! B-14: a drive with the sound of a steam engine plays the same sounds at
//! the same times as Electrip 1 (`tests/golden/steam_drive.jsonl`,
//! recorded from the scenario): the idle sound, blowing off steam and the
//! strokes with their pauses from the speed.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{POLL, assert_same, golden, play};

/// Electrip 1 rounds each pause between strokes to microseconds; over the
/// drive that adds up to some microseconds.
const TOLERANCE: f64 = 2e-5;

#[test]
fn steam_drive_matches_electrip_1() {
    let (sounds, _) = golden("steam_drive", 5);
    // Electrip 2 changes the speed at the end of a poll, Electrip 1 at the
    // start (B-10). Steam and strokes follow the speed one poll later; the
    // idle sound runs from the sound switch.
    let mut sounds: Vec<_> = sounds
        .into_iter()
        .map(|(time, sound, event)| {
            let lag = if sound.ends_with("idle.wav") {
                0.0
            } else {
                POLL
            };
            (time + lag, sound, event)
        })
        .collect();
    sounds.sort_by(|a, b| a.0.total_cmp(&b.0));
    let (played, _) = play("steam_drive");
    assert_same("sound event", &sounds, &played, TOLERANCE);
}
