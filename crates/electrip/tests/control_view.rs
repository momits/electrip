//! B-22: the options of the control view and what the window needs for
//! "focus" and the level bar come through the control channel; the
//! options outlive the app.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::App;
use common::diesel::{add_diesel, set_segment_sounds, toggle_sound};
use serde_json::json;
use tempfile::TempDir;

#[test]
fn the_view_options_are_kept() {
    let library = TempDir::new().unwrap();
    {
        let app = App::start_in(library.path(), &[]);
        let mut client = app.connect();
        let view = &client.state["view"];
        assert_eq!(
            view,
            &json!({"auto_focus": true, "only_active": false, "level_bar": true})
        );
        let view = json!({"auto_focus": false, "only_active": true, "level_bar": false});
        client
            .command(json!({"command": "set_view", "view": view}))
            .unwrap();
        assert_eq!(client.state["view"], view);
    }
    let app = App::start_in(library.path(), &[]);
    let client = app.connect();
    let view = json!({"auto_focus": false, "only_active": true, "level_bar": false});
    assert_eq!(client.state["view"], view);
}

#[test]
fn a_device_holds_focus_and_changes_locos() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    client.command(json!({"command": "add_loco"})).unwrap();
    client
        .command(json!({"command": "add_device", "device": 1, "kind": "Pad"}))
        .unwrap();
    let focus = json!({"type": "focus"});
    client
        .command(json!({"command": "bind", "kind": "Pad", "control": "x", "target": focus}))
        .unwrap();
    let input = |control: &str, value: f64| json!({"command": "input", "device": 1, "control": control, "value": value});
    client.command(input("x", 1.0)).unwrap();
    assert_eq!(client.state["devices"][0]["focus"], true);
    client.command(input("x", 0.0)).unwrap();
    assert_eq!(client.state["devices"][0]["focus"], false);
    let first = client.state["locos"][0]["id"].clone();
    let second = client.state["locos"][1]["id"].clone();
    assert_eq!(client.state["devices"][0]["loco"], first);
    client.command(input("dpright", 1.0)).unwrap();
    assert_eq!(client.state["devices"][0]["loco"], second);
}

#[test]
fn the_sound_level_rises_with_the_accel_sound_to_the_end_of_the_segment() {
    let app = App::start();
    let dir = TempDir::new().unwrap();
    let mut client = app.connect();
    add_diesel(&mut client, dir.path());
    set_segment_sounds(&mut client, dir.path(), 0.5);
    toggle_sound(&mut client);
    client.wait_for_loco("sound", json!("on"));
    assert_eq!(client.state["locos"][0]["sound_level"], 0.0);
    client
        .command(json!({"command": "set_speed", "loco": 1, "speed": 60.0}))
        .unwrap();
    let mut between = false;
    while client.state["locos"][0]["sound_level"] != 100.0 {
        let level = client.state["locos"][0]["sound_level"].as_f64().unwrap();
        between |= level > 0.0 && level < 100.0;
        client.expect_state();
    }
    assert!(between, "the level jumped");
    toggle_sound(&mut client);
    assert_eq!(client.state["locos"][0]["sound_level"], 0.0);
}
