//! B-03 with virtual gamepads of SDL: thirty gamepads control thirty
//! locos, each with its own number; plugging and unplugging is noticed
//! while running.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{Rig, Virtual};
use sdl3_sys::everything::*;
use serde_json::json;

#[test]
fn thirty_gamepads_come_and_go() {
    let mut rig = Rig::new();
    for _ in 0..30 {
        rig.apply(json!({"command": "add_loco"}));
    }
    let mut pads: Vec<_> = (0..30)
        .map(|_| Virtual::gamepad(c"Xbox Series X Controller", 0x045e, 0x0b12))
        .collect();
    rig.update(0.0);
    let locos: Vec<_> = rig.devices().into_iter().map(|(_, loco)| loco).collect();
    assert_eq!(locos, (1..=30).map(Some).collect::<Vec<_>>());
    assert_eq!(rig.numbers(), (1..=30).collect::<Vec<_>>());

    // Unplugged while driving, loco 5 keeps its speed.
    pads[4].axis(SDL_GAMEPAD_AXIS_LEFTY, -1.0);
    rig.update(1.0);
    let speed = rig.loco(5).station_state().step;
    assert!(speed > 0);
    pads.remove(4).detach();
    rig.update(1.0);
    assert_eq!(rig.devices().len(), 29);
    assert_eq!(rig.loco(5).station_state().step, speed);

    // A new pad gets the free loco.
    let pad = Virtual::gamepad(c"PS5 Controller", 0x054c, 0x0ce6);
    rig.update(0.0);
    assert_eq!(
        rig.devices().last().unwrap(),
        &("PS5 Controller".into(), Some(5))
    );
    assert_eq!(rig.numbers().last(), Some(&5));
    pad.detach();
}
