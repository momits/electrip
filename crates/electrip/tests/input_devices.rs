//! N-01 over the control channel: three virtual input devices of
//! different types control three locos at once, each through the mapping
//! of its type. Holding "next loco" scrolls through the locos (B-23).

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::{App, Client};
use serde_json::{Value, json};
use std::time::{Duration, Instant};

/// The devices: an Xbox pad with the standard mapping, a PlayStation pad
/// driving with the right stick and a joystick with numbered controls.
const DEVICES: [(u32, &str); 3] = [
    (1, "Xbox Series X Controller"),
    (2, "PS5 Controller"),
    (3, "Logitech Extreme 3D"),
];

/// Adds three locos that take one second to accelerate, the action
/// "Licht" on F0 of loco 3, the mappings and the devices.
fn set_up(client: &mut Client) {
    let mut commands = vec![json!({"command": "add_action", "name": "Licht"})];
    for loco in 1..=3 {
        commands.push(json!({"command": "add_loco"}));
        commands.push(json!({"command": "set_accel_duration", "loco": loco, "seconds": 1}));
    }
    commands.push(
        json!({"command": "add_function", "loco": 3, "function": {"action": 1, "number": 0}}),
    );
    for (kind, control, target) in [
        ("PS5 Controller", "righty", json!({"type": "drive"})),
        ("PS5 Controller", "y", json!({"type": "reverse"})),
        (
            "Logitech Extreme 3D",
            "axis1",
            json!({"type": "drive", "dead_zone": 0.1}),
        ),
        ("Logitech Extreme 3D", "button1", json!({"type": "reverse"})),
        (
            "Logitech Extreme 3D",
            "button0",
            json!({"type": "action", "action": 1}),
        ),
    ] {
        commands
            .push(json!({"command": "bind", "kind": kind, "control": control, "target": target}));
    }
    for (device, kind) in DEVICES {
        commands.push(json!({"command": "add_device", "device": device, "kind": kind}));
    }
    for command in commands {
        client.command(command).unwrap();
    }
}

fn input(client: &mut Client, device: u32, control: &str, value: f64) {
    client
        .command(json!({"command": "input", "device": device, "control": control, "value": value}))
        .unwrap();
}

fn press(client: &mut Client, device: u32, control: &str) {
    input(client, device, control, 1.0);
    input(client, device, control, 0.0);
}

fn locos(client: &Client, field: &str) -> Vec<Value> {
    let locos = client.state["locos"].as_array().unwrap();
    locos.iter().map(|loco| loco[field].clone()).collect()
}

#[test]
fn three_devices_drive_three_locos_with_their_own_mappings() {
    let app = App::start();
    let mut client = app.connect();
    set_up(&mut client);
    let devices = client.state["devices"].as_array().unwrap();
    let controlled: Vec<&Value> = devices.iter().map(|d| &d["loco"]).collect();
    assert_eq!(controlled, [1, 2, 3]);

    for (device, axis) in [(1, "lefty"), (2, "righty"), (3, "axis1")] {
        input(&mut client, device, axis, -1.0);
    }
    while locos(&client, "speed") != [100.0; 3] {
        client.expect_state();
    }
    for (device, axis) in [(1, "lefty"), (2, "righty"), (3, "axis1")] {
        input(&mut client, device, axis, 0.0);
    }

    press(&mut client, 1, "b");
    press(&mut client, 2, "y");
    assert_eq!(locos(&client, "forward"), [false, false, true]);
    press(&mut client, 3, "button1");
    assert_eq!(locos(&client, "forward"), [false, false, false]);
    assert_eq!(locos(&client, "speed"), [0.0; 3]);
}

#[test]
fn a_button_of_a_device_switches_a_function_of_its_loco() {
    let app = App::start();
    let mut client = app.connect();
    set_up(&mut client);
    press(&mut client, 3, "button0");
    assert_eq!(client.state["locos"][2]["functions"][0]["on"], true);
}

#[test]
fn holding_next_loco_scrolls_after_500_ms() {
    let app = App::start();
    let mut client = app.connect();
    set_up(&mut client);
    for _ in 4..=6 {
        client.command(json!({"command": "add_loco"})).unwrap();
    }
    let start = Instant::now();
    input(&mut client, 1, "dpright", 1.0);
    assert_eq!(client.state["devices"][0]["loco"], 4);
    while client.state["devices"][0]["loco"] != 6 {
        client.expect_state();
    }
    assert!(start.elapsed() >= Duration::from_millis(560));
    input(&mut client, 1, "dpright", 0.0);
    press(&mut client, 1, "dpleft");
    assert_eq!(client.state["devices"][0]["loco"], 5);
}

#[test]
fn an_unknown_device_is_an_error() {
    let app = App::start();
    let mut client = app.connect();
    let error =
        client.command(json!({"command": "input", "device": 9, "control": "a", "value": 1}));
    assert_eq!(error, Err("there is no device with id 9".into()));
}
