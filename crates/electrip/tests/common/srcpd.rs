//! Helpers for the tests marked `#[ignore]` that need srcpd on bus 1
//! (`cargo xtask sim up`).

// Test code: unwrap and panic are allowed (AGENTS.md).
#![allow(clippy::unwrap_used, clippy::panic)]

use super::{App, Client};
use electrip_core::station::{CommandStation, StationEvent};
use electrip_station_srcp::{DEFAULT_PORT, SrcpStation};
use serde_json::json;
use std::time::{Duration, Instant};

/// A client of `app`, connected to srcpd on bus 1.
pub fn connect_to_srcpd(app: &App) -> Client {
    let mut client = app.connect();
    client
        .command(
            json!({"command": "set_server", "host": "127.0.0.1", "port": DEFAULT_PORT, "bus": 1}),
        )
        .unwrap();
    client.command(json!({"command": "connect"})).unwrap();
    client
}

/// A second connection to srcpd that watches what the app sends.
pub fn observer() -> SrcpStation {
    SrcpStation::connect("127.0.0.1", DEFAULT_PORT, 1).unwrap()
}

/// Waits until `station` reports an event that `matches`.
pub fn expect_event(station: &mut SrcpStation, matches: impl Fn(&StationEvent) -> bool) {
    let deadline = Instant::now() + Duration::from_secs(5);
    while Instant::now() < deadline {
        if station.events().iter().any(&matches) {
            return;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    panic!("ERROR srcpd did not report the expected event");
}
