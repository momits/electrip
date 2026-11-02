//! B-09: a change of Vmax, speed steps or protocol resets the speed curve
//! only when confirmed; without the confirmation nothing changes.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{App, Client};
use serde_json::{Value, json};

const NOT_CONFIRMED: &str = "this change resets the speed curve and needs a confirmation";

/// A client with one loco whose curve has an extra point.
fn loco_with_bent_curve(app: &App) -> Client {
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    client
        .command(json!({"command": "add_curve_point", "loco": 1, "speed": 50, "step": 20}))
        .unwrap();
    client
}

fn changes() -> [Value; 3] {
    [
        json!({"command": "set_max_speed", "loco": 1, "max_speed": 80}),
        json!({"command": "set_speed_steps", "loco": 1, "speed_steps": 28}),
        json!({"command": "set_protocol", "loco": 1, "protocol": "motorola1"}),
    ]
}

#[test]
fn unconfirmed_change_leaves_everything_unchanged() {
    let app = App::start();
    let mut client = loco_with_bent_curve(&app);
    let before = client.state.clone();
    for change in changes() {
        assert_eq!(client.command(change), Err(NOT_CONFIRMED.into()));
    }
    assert_eq!(app.connect().state, before);
}

#[test]
fn confirmed_change_resets_the_curve() {
    let expected = [
        (json!(80.0), json!(128), json!([[0.0, 0.0], [80.0, 128.0]])),
        (json!(100.0), json!(28), json!([[0.0, 0.0], [100.0, 28.0]])),
        (json!(100.0), json!(14), json!([[0.0, 0.0], [100.0, 14.0]])),
    ];
    for (mut change, (max_speed, steps, curve)) in changes().into_iter().zip(expected) {
        let app = App::start();
        let mut client = loco_with_bent_curve(&app);
        change["confirmed"] = json!(true);
        client.command(change).unwrap();
        let loco = &client.state["locos"][0];
        assert_eq!(loco["max_speed"], max_speed);
        assert_eq!(loco["decoder"]["speed_steps"], steps);
        assert_eq!(loco["speed_curve"], curve);
    }
}
