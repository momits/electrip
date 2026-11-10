//! N-08: the app is operated through the control channel.

mod common;

use common::App;
use serde_json::json;

#[test]
fn greets_with_version_and_state() {
    let app = App::start();
    let mut client = app.connect();
    // The output devices depend on the computer (N-05).
    let devices = client
        .state
        .as_object_mut()
        .unwrap()
        .remove("audio_devices");
    assert!(devices.unwrap().is_array());
    assert_eq!(
        client.state,
        json!({"locos": [], "actions": [], "mappings": [], "devices": [], "import_report": [], "audio_targets": {}, "audio_latency": {}, "audio_conflicts": [], "configuration": "Electrip", "configurations": ["Electrip"], "station": {"kind": "srcp", "host": "localhost", "port": 4303, "bus": 1, "power_on_start": true, "connected": false, "track_power": false}, "view": {"auto_focus": true, "only_active": false}})
    );
}

#[test]
fn executes_commands_and_reports_errors() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    client
        .command(json!({"command": "set_address", "loco": 1, "address": 3}))
        .unwrap();
    assert_eq!(client.state["locos"][0]["decoder"]["address"], 3);

    let error = client.command(json!({"command": "set_address", "loco": 1, "address": 200}));
    assert_eq!(error, Err("the address must be between 1 and 127".into()));
    let reply = client.send_line("not json");
    assert_eq!(reply["ok"], false);
    assert!(
        reply["error"]
            .as_str()
            .unwrap()
            .starts_with("invalid command")
    );
}

#[test]
fn reports_changes_to_all_clients() {
    let app = App::start();
    let mut first = app.connect();
    let mut second = app.connect();
    first.command(json!({"command": "add_loco"})).unwrap();
    second.expect_state();
    assert_eq!(second.state, first.state);
    assert_eq!(second.state["locos"][0]["id"], 1);
}
