//! B-02 with a virtual joystick of SDL: each built-in action works on a
//! button, an axis or a hat direction. One test per file, because SDL
//! must run on the main thread.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{Rig, Virtual};
use electrip_core::driving_sound::SoundState;
use sdl3_sys::everything::*;
use serde_json::json;

#[test]
fn built_in_actions_on_buttons_axes_and_hats() {
    let mut rig = Rig::new();
    rig.apply(json!({"command": "add_loco"}));
    rig.apply(json!({"command": "set_accel_duration", "loco": 1, "seconds": 1}));
    rig.apply(json!({"command": "set_engine", "loco": 1, "engine": "diesel"}));
    let idle = json!({"command": "set_engine_sound", "loco": 1, "sound": "idle", "path": "idle"});
    rig.apply(idle);
    let stick = Virtual::joystick(c"Flight Stick", 4, 12, 1);
    rig.update(0.0);
    for (control, target) in [
        ("axis1", "drive"),
        ("button3", "focus"),
        ("hat0_up", "toggle_sound"),
        ("axis2", "emergency_stop"),
        ("hat0_down", "reverse"),
        ("button4", "toggle_power"),
    ] {
        let target = json!({"type": target});
        rig.apply(json!({"command": "bind", "kind": "Flight Stick", "control": control, "target": target}));
    }

    stick.joystick_button(3, true);
    rig.update(0.0);
    assert!(rig.host.session().devices()[0].focus);
    stick.joystick_button(3, false);
    rig.update(0.0);
    assert!(!rig.host.session().devices()[0].focus);

    stick.hat(0, SDL_HAT_UP);
    rig.update(0.0);
    stick.hat(0, SDL_HAT_CENTERED);
    rig.update(0.0);
    assert_eq!(rig.loco(1).sound.state(), SoundState::Starting);
    rig.update(1.0);

    stick.joystick_axis(1, -1.0);
    rig.update(0.5);
    stick.joystick_axis(1, 0.0);
    assert!(rig.loco(1).station_state().step > 0);
    stick.joystick_axis(2, 1.0);
    rig.update(0.0);
    assert_eq!(rig.loco(1).station_state().step, 0);
    stick.joystick_axis(2, 0.0);

    stick.hat(0, SDL_HAT_DOWN);
    rig.update(0.0);
    assert!(!rig.loco(1).station_state().forward);

    stick.joystick_button(4, true);
    rig.update(0.0);
    assert!(!rig.host.session().station().track_power);
}
