//! B-17: event sounds start, fade in and play to the end like in
//! Electrip 1 (`tests/golden/event_sounds.jsonl`, recorded from the
//! scenario), as far as Electrip 2 checks the conditions the same way.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{Event, POLL, assert_same, golden, play};

/// The whistle when starting and the squeal when braking, up to its first
/// end.
fn compared(events: Vec<Event>) -> Vec<Event> {
    let mut events: Vec<_> = events
        .into_iter()
        .filter(|e| !e.1.ends_with("rolling.wav"))
        .collect();
    events.truncate(3);
    events
}

#[test]
fn event_sounds_match_electrip_1() {
    let (sounds, _) = golden("event_sounds", 5);
    let (played, _) = play("event_sounds");
    // Electrip 1 checks the acceleration of the poll before (Q-013), but
    // changes the speed at the start of a poll, Electrip 2 at the end
    // (B-10): the whistle starts one poll earlier, the squeal one later.
    let tolerance = POLL + 1e-9;
    assert_same(
        "sound",
        &compared(sounds),
        &compared(played.clone()),
        tolerance,
    );
    // Unlike Electrip 1 (Q-013): the first press activates the rolling
    // sound at once, and the squeal fades out when the loco stands, as
    // it no longer brakes.
    let rest: Vec<_> = played[2..]
        .iter()
        .map(|e| (e.1.as_str(), e.2.as_str()))
        .collect();
    assert_eq!(
        rest,
        [
            ("event/rolling.wav", "start 1000"),
            ("event/rolling.wav", "fade_out 1000"),
            ("event/rolling.wav", "end"),
            ("event/squeal.wav", "start"),
            ("event/squeal.wav", "fade_out 500"),
            ("event/squeal.wav", "end"),
        ]
    );
}
