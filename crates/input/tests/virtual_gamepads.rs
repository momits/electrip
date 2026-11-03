//! N-01 with virtual devices of SDL: an Xbox pad, a PlayStation pad and a
//! joystick control three locos at once, each through the mapping of its
//! type. Also covers the built-in actions over a device (B-07, B-10,
//! B-23, N-07).

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{Rig, Virtual};
use sdl3_sys::everything::*;
use serde_json::json;

#[test]
fn three_device_types_drive_three_locos() {
    let mut rig = Rig::new();
    rig.apply(json!({"command": "add_action", "name": "Licht"}));
    for loco in 1..=4 {
        rig.apply(json!({"command": "add_loco"}));
        rig.apply(json!({"command": "set_accel_duration", "loco": loco, "seconds": 1}));
        rig.apply(json!({"command": "set_brake_duration", "loco": loco, "seconds": 1}));
    }
    rig.apply(
        json!({"command": "add_function", "loco": 3, "function": {"action": 1, "number": 0}}),
    );
    let xbox = Virtual::gamepad(c"Xbox Series X Controller", 0x045e, 0x0b12);
    let ps = Virtual::gamepad(c"PS5 Controller", 0x054c, 0x0ce6);
    let stick = Virtual::joystick(c"Flight Stick", 4, 12, 1);
    rig.update(0.0);
    let kinds: Vec<_> = rig.devices().into_iter().map(|(kind, _)| kind).collect();
    assert_eq!(
        kinds,
        ["Xbox Series X Controller", "PS5 Controller", "Flight Stick"]
    );
    for (kind, control, target) in [
        ("PS5 Controller", "righty", json!({"type": "drive"})),
        ("PS5 Controller", "y", json!({"type": "reverse"})),
        (
            "Flight Stick",
            "axis1",
            json!({"type": "drive", "dead_zone": 0.1}),
        ),
        (
            "Flight Stick",
            "button0",
            json!({"type": "action", "action": 1}),
        ),
        ("Flight Stick", "hat0_right", json!({"type": "next_loco"})),
    ] {
        rig.apply(json!({"command": "bind", "kind": kind, "control": control, "target": target}));
    }

    // Each device drives its own loco with its own controls, up is negative.
    xbox.axis(SDL_GAMEPAD_AXIS_LEFTY, -1.0);
    ps.axis(SDL_GAMEPAD_AXIS_RIGHTY, -1.0);
    ps.axis(SDL_GAMEPAD_AXIS_LEFTY, -1.0);
    stick.joystick_axis(1, -0.05);
    rig.update(1.0);
    let max = rig.loco(1).station_state().step;
    assert!(max > 0);
    assert_eq!(rig.loco(2).station_state().step, max);
    // Inside the dead zone of the joystick.
    assert_eq!(rig.loco(3).station_state().step, 0);

    // Reverse on the PlayStation pad, the action on the joystick.
    ps.button(SDL_GAMEPAD_BUTTON_NORTH, true);
    stick.joystick_button(0, true);
    rig.update(0.0);
    assert_eq!(rig.loco(2).station_state().step, 0);
    assert!(!rig.loco(2).station_state().forward);
    assert!(rig.loco(3).station_state().function(0));

    // The A button of the Xbox pad switches the track power off.
    xbox.button(SDL_GAMEPAD_BUTTON_SOUTH, true);
    rig.update(0.0);
    assert!(!rig.host.session().station().track_power);

    // The hat of the joystick moves it to the free loco 4.
    stick.hat(0, SDL_HAT_RIGHT);
    rig.update(0.0);
    stick.hat(0, SDL_HAT_CENTERED);
    rig.update(0.0);
    assert_eq!(rig.devices()[2].1, Some(4));
}
