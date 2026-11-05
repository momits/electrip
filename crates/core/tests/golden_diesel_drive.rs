//! B-11, B-12: a drive with the sound of a combustion engine plays the same
//! sounds at the same times as Electrip 1 (`tests/golden/diesel_drive.jsonl`,
//! recorded from the scenario).
//! B-13: the loco starts and stops with the sound at the same times as in
//! Electrip 1 (the SRCP commands to srcpd). The steps in between are left
//! out; they are up to the acceleration (B-10).

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{Event, assert_same, golden, play};

/// The golden file rounds times to microseconds.
const TOLERANCE: f64 = 1e-6;

/// The states where the loco starts or stops.
fn starts_and_stops(states: &[Event]) -> Vec<Event> {
    let mut stopped = true;
    let mut changes = Vec::new();
    for state in states {
        let step = state.2.split(' ').nth(1).unwrap();
        if (step == "0") != stopped {
            stopped = !stopped;
            changes.push(state.clone());
        }
    }
    changes
}

#[test]
fn diesel_drive_matches_electrip_1() {
    let (sounds, states) = golden("diesel_drive", 3);
    let (played, sent) = play("diesel_drive");
    assert_same("sound event", &sounds, &played, TOLERANCE);
    let (states, sent) = (starts_and_stops(&states), starts_and_stops(&sent));
    assert_eq!(states.len(), 2, "one start and one stop: {states:?}");
    assert_same("start or stop", &states, &sent, TOLERANCE);
}
