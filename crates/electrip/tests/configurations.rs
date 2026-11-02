//! B-21, B-24: configurations are created, switched, renamed, removed and
//! exported through the control channel; they outlive the app, and
//! `-f/--file` opens one at the start.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{App, Client};
use serde_json::{Value, json};
use std::fs;
use tempfile::TempDir;

fn names(client: &Client) -> &Value {
    &client.state["configurations"]
}

#[test]
fn configurations_are_managed_and_kept() {
    let library = TempDir::new().unwrap();
    {
        let app = App::start_in(library.path(), &[]);
        let mut client = app.connect();
        assert_eq!(client.state["configuration"], "Electrip");
        client.command(json!({"command": "add_loco"})).unwrap();
        client
            .command(json!({"command": "new_configuration", "name": "Keller"}))
            .unwrap();
        assert_eq!(client.state["locos"], json!([]));
        client
            .command(json!({"command": "set_server", "host": "srcp", "port": 4303, "bus": 1}))
            .unwrap();
        client
            .command(json!({"command": "rename_configuration", "name": "Dachboden"}))
            .unwrap();
        assert_eq!(names(&client), &json!(["Dachboden", "Electrip"]));
        let error = client
            .command(json!({"command": "remove_configuration", "name": "Dachboden"}))
            .unwrap_err();
        assert_eq!(error, "the configuration \"Dachboden\" is open");
        client
            .command(json!({"command": "open_configuration", "name": "Electrip"}))
            .unwrap();
        assert_eq!(client.state["locos"].as_array().unwrap().len(), 1);
    }
    let app = App::start_in(library.path(), &["--file", "Dachboden"]);
    let mut client = app.connect();
    assert_eq!(client.state["configuration"], "Dachboden");
    assert_eq!(client.state["station"]["host"], "srcp");
    client
        .command(json!({"command": "remove_configuration", "name": "Electrip"}))
        .unwrap();
    assert_eq!(names(&client), &json!(["Dachboden"]));
}

#[test]
fn export_writes_the_configuration_to_a_file() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    let target = TempDir::new().unwrap();
    let path = target.path().join("anlage.json");
    client
        .command(json!({"command": "export_configuration", "path": path}))
        .unwrap();
    let file: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
    assert_eq!(file["locos"][0]["name"], client.state["locos"][0]["name"]);
    assert_eq!(file["station"]["host"], "localhost");
}
