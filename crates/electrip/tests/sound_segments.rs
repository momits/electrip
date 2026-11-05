//! B-15: sound segments are inserted, removed and moved through the control
//! channel, and every client sees them.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::App;
use serde_json::{Value, json};

fn starts(state: &Value) -> Vec<f64> {
    let segments = state["locos"][0]["sound_model"]["segments"]
        .as_array()
        .unwrap();
    segments
        .iter()
        .map(|s| s["start"].as_f64().unwrap())
        .collect()
}

#[test]
fn segments_are_edited() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    assert_eq!(client.state["locos"][0]["sound_model"], json!(null));
    let insert = json!({"command": "insert_segment", "loco": 1, "segment": 0});
    assert_eq!(
        client.command(insert.clone()),
        Err("the loco has no sound".into())
    );

    client
        .command(json!({"command": "set_engine", "loco": 1, "engine": "diesel"}))
        .unwrap();
    assert_eq!(client.state["locos"][0]["sound_model"]["engine"], "diesel");
    client.command(insert.clone()).unwrap();
    client.command(insert).unwrap();
    assert_eq!(starts(&client.state), [0.0, 25.0, 50.0]);

    let border = json!({"command": "move_segment_border", "loco": 1, "segment": 2, "speed": 70});
    client.command(border).unwrap();
    client
        .command(json!({"command": "remove_segment", "loco": 1, "segment": 1}))
        .unwrap();
    assert_eq!(starts(&client.state), [0.0, 70.0]);
    assert_eq!(app.connect().state, client.state);
}

#[test]
fn removing_the_last_segment_asks_for_a_confirmation() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    client
        .command(json!({"command": "set_engine", "loco": 1, "engine": "steam"}))
        .unwrap();

    let remove = json!({"command": "remove_segment", "loco": 1, "segment": 0});
    assert_eq!(
        client.command(remove),
        Err("this change resets the sounds of the loco and needs a confirmation".into())
    );
    assert_eq!(starts(&client.state), [0.0]);
    let confirmed =
        json!({"command": "remove_segment", "loco": 1, "segment": 0, "confirmed": true});
    client.command(confirmed).unwrap();
    assert_eq!(client.state["locos"][0]["sound_model"], json!(null));
}
