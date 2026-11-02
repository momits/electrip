//! B-08: control points of the speed curve are added, moved and removed
//! through the control channel; the ends stay and only change their step.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{App, Client};
use serde_json::{Value, json};

/// Sends a curve command for loco 1 and returns its new curve.
fn curve_after(client: &mut Client, mut command: Value) -> Value {
    command["loco"] = json!(1);
    client.command(command).unwrap();
    client.state["locos"][0]["speed_curve"].clone()
}

#[test]
fn points_are_added_moved_and_removed() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();

    let add = json!({"command": "add_curve_point", "speed": 50, "step": 20});
    let curve = curve_after(&mut client, add);
    assert_eq!(curve, json!([[0.0, 0.0], [50.0, 20.0], [100.0, 128.0]]));

    let move_inner = json!({"command": "move_curve_point", "point": 1, "speed": 60, "step": 30});
    let curve = curve_after(&mut client, move_inner);
    assert_eq!(curve, json!([[0.0, 0.0], [60.0, 30.0], [100.0, 128.0]]));

    let move_first = json!({"command": "move_curve_point", "point": 0, "speed": 10, "step": 5});
    let curve = curve_after(&mut client, move_first);
    assert_eq!(curve, json!([[0.0, 5.0], [60.0, 30.0], [100.0, 128.0]]));

    let remove = json!({"command": "remove_curve_point", "point": 1});
    let curve = curve_after(&mut client, remove);
    assert_eq!(curve, json!([[0.0, 5.0], [100.0, 128.0]]));

    // Every client sees the result.
    assert_eq!(app.connect().state, client.state);
}

#[test]
fn ends_cannot_be_removed() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    for point in [0, 1] {
        let remove = json!({"command": "remove_curve_point", "point": point});
        let curve = curve_after(&mut client, remove);
        assert_eq!(curve, json!([[0.0, 0.0], [100.0, 128.0]]));
    }
}

#[test]
fn unknown_loco_is_an_error() {
    let app = App::start();
    let mut client = app.connect();
    let error =
        client.command(json!({"command": "add_curve_point", "loco": 1, "speed": 50, "step": 20}));
    assert_eq!(error, Err("there is no loco with id 1".into()));
}
