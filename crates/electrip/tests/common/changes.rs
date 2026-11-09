//! Helpers for the tests of changes by another program at the command
//! station (N-03).

use super::Client;
use electrip_core::decoder::{Decoder, Protocol};
use electrip_core::station::{CommandStation, LocoState};
use serde_json::json;

pub fn connect_to_z21(client: &mut Client, port: u16) {
    let server = json!({"command": "set_server", "kind": "z21", "host": "127.0.0.1", "port": port, "bus": 0});
    client.command(server).unwrap();
    client.command(json!({"command": "connect"})).unwrap();
}

pub fn add_loco_at(client: &mut Client, address: u16) {
    client.command(json!({"command": "add_loco"})).unwrap();
    let command = json!({"command": "set_address", "loco": 1, "address": address});
    client.command(command).unwrap();
}

/// Another program drives the loco back at step 64 of 128, i.e. about half
/// of Vmax.
pub fn drive_back_at_half(other: &mut dyn CommandStation, address: u16) {
    let decoder = Decoder::new(Protocol::DccShort, address, 128).unwrap();
    let state = LocoState {
        forward: false,
        step: 64,
        functions: 0,
    };
    other.set_loco(&decoder, &state).unwrap();
}

/// Loco 1 of the app drives as [`drive_back_at_half`] set it. The
/// command station may report the loco standing first.
pub fn expect_back_at_half(client: &mut Client) {
    let speed = |client: &Client| client.state["locos"][0]["speed"].as_f64().unwrap();
    while speed(client) == 0.0 {
        client.expect_state();
    }
    assert_eq!(client.state["locos"][0]["forward"], false);
    assert!((speed(client) - 50.4).abs() < 0.1, "{}", speed(client));
}
