//! B-21, B-06: a configuration file of Electrip 1 is imported through the
//! control channel, and every client sees the result and the report.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::App;
use serde_json::json;
use std::env;
use std::fs;
use std::path::Path;

#[test]
fn a_file_of_electrip_1_is_imported() {
    let app = App::start();
    let mut client = app.connect();
    let path =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/corpus/configs/settings.json");
    client
        .command(json!({"command": "import_electrip1", "path": path}))
        .unwrap();
    let state = &client.state;
    assert_eq!(state["locos"][0]["name"], "BR 216");
    assert_eq!(
        state["locos"][1]["decoder"],
        json!({"protocol": "motorola2", "address": 78, "speed_steps": 28})
    );
    assert_eq!(
        state["station"],
        json!({"host": "192.168.0.111", "port": 4304, "bus": 2, "connected": false})
    );
    assert_eq!(state["import_report"], json!([]));
    assert_eq!(app.connect().state, client.state);
}

#[test]
fn the_report_names_locos_that_became_dcc_long() {
    let path = env::temp_dir().join(format!("electrip1-import-{}.json", std::process::id()));
    let file = json!({
        "locos": [{"name": "V 100", "protocol": "N 1", "address": 200,
                   "speed_control_points": [[0, 0], [100, 128]]}],
        "server": {}
    });
    fs::write(&path, file.to_string()).unwrap();
    let app = App::start();
    let mut client = app.connect();
    let result = client.command(json!({"command": "import_electrip1", "path": path}));
    fs::remove_file(&path).unwrap();
    result.unwrap();
    assert_eq!(client.state["locos"][0]["decoder"]["protocol"], "dcc_long");
    assert_eq!(
        client.state["import_report"],
        json!(["V 100: address 200 is too high for DCC short, changed to DCC long"])
    );
}

#[test]
fn a_missing_file_names_the_reason() {
    let app = App::start();
    let mut client = app.connect();
    let error = client
        .command(json!({"command": "import_electrip1", "path": "/nonexistent/electrip.json"}))
        .unwrap_err();
    assert!(error.starts_with("cannot read the file: "), "{error}");
}
