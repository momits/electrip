//! B-17 over the control channel: event sounds are added and removed, and
//! an action switches them active and inactive. The app has no audio
//! output yet, so the sounds stay silent.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::App;
use serde_json::json;

#[test]
fn event_sounds_are_edited_and_switched() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    client
        .command(json!({"command": "add_action", "name": "Bremsen"}))
        .unwrap();
    for name in ["Quietschen", "Pfiff"] {
        let sound = json!({"action": 1, "name": name, "path": "/no/sound.wav", "max_accel": -2.0});
        client
            .command(json!({"command": "add_event_sound", "loco": 1, "sound": sound}))
            .unwrap();
    }
    client
        .command(json!({"command": "remove_event_sound", "loco": 1, "index": 1}))
        .unwrap();
    let sounds = &client.state["locos"][0]["event_sounds"];
    assert_eq!(sounds.as_array().unwrap().len(), 1);
    assert_eq!(sounds[0]["name"], "Quietschen");
    assert_eq!(sounds[0]["max_accel"], -2.0);
    assert_eq!(sounds[0]["active"], true);

    client
        .command(json!({"command": "trigger_action", "loco": 1, "action": 1, "pressed": true}))
        .unwrap();
    assert_eq!(client.state["locos"][0]["event_sounds"][0]["active"], false);
    assert_eq!(app.connect().state, client.state);
}
