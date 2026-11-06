//! B-16 over the control channel: sound functions are added, moved and
//! removed like functions, and an action switches them. The app has no
//! audio output yet, so the sounds stay silent.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::App;
use serde_json::{Value, json};

fn names(state: &Value) -> Vec<&str> {
    let functions = state["locos"][0]["sound_functions"].as_array().unwrap();
    functions
        .iter()
        .map(|f| f["name"].as_str().unwrap())
        .collect()
}

#[test]
fn sound_functions_are_edited_and_switched() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    client
        .command(json!({"command": "add_action", "name": "Hupe"}))
        .unwrap();
    for (name, mode) in [("Hupe", "switch"), ("Pfiff", "tap"), ("Glocke", "push")] {
        let function = json!({"action": 1, "name": name, "mode": mode, "path": "/no/sound.wav"});
        client
            .command(json!({"command": "add_sound_function", "loco": 1, "function": function}))
            .unwrap();
    }
    client
        .command(json!({"command": "move_sound_function", "loco": 1, "index": 0, "position": 2}))
        .unwrap();
    client
        .command(json!({"command": "remove_sound_function", "loco": 1, "index": 0}))
        .unwrap();
    assert_eq!(names(&client.state), ["Glocke", "Hupe"]);

    client
        .command(json!({"command": "trigger_action", "loco": 1, "action": 1, "pressed": true}))
        .unwrap();
    let functions = &client.state["locos"][0]["sound_functions"];
    assert_eq!(functions[0]["on"], true);
    assert_eq!(functions[1]["on"], true);
    assert_eq!(app.connect().state, client.state);
}
