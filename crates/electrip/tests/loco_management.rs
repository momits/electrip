//! B-04: locos are added, renamed, removed and reordered through the control
//! channel, and every client sees the loco list.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{App, Client};
use serde_json::{Value, json};

/// The given field of every loco, in the order of the loco list.
fn field(client: &Client, key: &str) -> Vec<Value> {
    let locos = client.state["locos"].as_array().unwrap();
    locos.iter().map(|l| l[key].clone()).collect()
}

#[test]
fn locos_are_added_renamed_removed_and_reordered() {
    let app = App::start();
    let mut client = app.connect();
    for _ in 0..3 {
        client.command(json!({"command": "add_loco"})).unwrap();
    }
    assert_eq!(field(&client, "name"), ["Unbenannte Lok"; 3]);

    let rename = json!({"command": "rename_loco", "loco": 2, "name": "BR 218"});
    client.command(rename).unwrap();
    assert_eq!(
        field(&client, "name"),
        ["Unbenannte Lok", "BR 218", "Unbenannte Lok"]
    );

    let order = json!({"command": "move_loco", "loco": 3, "position": 0});
    client.command(order).unwrap();
    assert_eq!(field(&client, "id"), [3, 1, 2]);

    client
        .command(json!({"command": "remove_loco", "loco": 1}))
        .unwrap();
    assert_eq!(field(&client, "id"), [3, 2]);
    assert_eq!(field(&client, "name"), ["Unbenannte Lok", "BR 218"]);

    // Every client sees the result.
    assert_eq!(app.connect().state, client.state);
}

#[test]
fn failed_commands_name_the_reason() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();

    let remove = json!({"command": "remove_loco", "loco": 2});
    assert_eq!(
        client.command(remove),
        Err("there is no loco with id 2".into())
    );
    let order = json!({"command": "move_loco", "loco": 1, "position": 1});
    assert_eq!(
        client.command(order),
        Err("there is no position 1 in the list".into())
    );
    assert_eq!(field(&client, "id"), [1]);
}
