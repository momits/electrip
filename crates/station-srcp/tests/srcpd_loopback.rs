//! Scenario tests against srcpd with a loopback bus (N-02). They need
//! srcpd on port 4303; `cargo xtask sim up` starts it and runs them. Each
//! test uses its own loco addresses, since the tests share the bus. An INFO
//! session starts with the current state, so each test first expects a state
//! that differs from the one it leaves behind.

// Test code: unwrap and panic are allowed (AGENTS.md).
#![allow(clippy::unwrap_used, clippy::panic)]

use electrip_core::decoder::{Decoder, Protocol};
use electrip_core::station::{CommandStation, LocoState, MAX_FUNCTION, StationEvent};
use electrip_station_srcp::{DEFAULT_PORT, SrcpStation};
use std::time::{Duration, Instant};

const BUS: u16 = 1;

fn connect() -> SrcpStation {
    SrcpStation::connect("127.0.0.1", DEFAULT_PORT, BUS).unwrap()
}

fn dcc(address: u16) -> Decoder {
    Decoder::new(Protocol::DccShort, address, 28).unwrap()
}

/// Waits until `station` reports `expected`.
fn expect_event(station: &mut SrcpStation, expected: StationEvent) {
    let deadline = Instant::now() + Duration::from_secs(5);
    let mut seen = Vec::new();
    while Instant::now() < deadline {
        let events = station.events();
        if events.contains(&expected) {
            return;
        }
        seen.extend(events);
        std::thread::sleep(Duration::from_millis(20));
    }
    panic!("ERROR expected {expected:?}, got {seen:?}");
}

fn loco_event(address: u16, state: LocoState) -> StationEvent {
    StationEvent::Loco { address, state }
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn connects_and_disconnects() {
    let station = connect();
    drop(station);
    let mut station = connect();
    station.set_loco(&dcc(20), &LocoState::default()).unwrap();
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn reports_connection_errors() {
    let error = SrcpStation::connect("127.0.0.1", 1, BUS).err().unwrap();
    assert!(
        error
            .0
            .starts_with("cannot reach the SRCP server 127.0.0.1:1"),
        "{error}"
    );
    let error = SrcpStation::connect("127.0.0.1", DEFAULT_PORT, 7)
        .err()
        .unwrap();
    assert!(
        error.0.starts_with("the SRCP server has no bus 7: "),
        "{error}"
    );
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn switches_power() {
    let mut station = connect();
    station.set_power(false).unwrap();
    expect_event(&mut station, StationEvent::Power(false));
    station.set_power(true).unwrap();
    expect_event(&mut station, StationEvent::Power(true));
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn drives_a_loco() {
    let mut station = connect();
    for (forward, step) in [(true, 12), (false, 3)] {
        let state = LocoState {
            forward,
            step,
            functions: 0,
        };
        station.set_loco(&dcc(21), &state).unwrap();
        expect_event(&mut station, loco_event(21, state));
    }
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn drives_a_loco_after_a_protocol_change() {
    let mut station = connect();
    let state = LocoState {
        forward: true,
        step: 100,
        functions: 0,
    };
    let dcc128 = Decoder::new(Protocol::DccLong, 22, 128).unwrap();
    station.set_loco(&dcc128, &state).unwrap();
    expect_event(&mut station, loco_event(22, state));
    let motorola = Decoder::new(Protocol::Motorola2, 22, 14).unwrap();
    let state = LocoState { step: 9, ..state };
    station.set_loco(&motorola, &state).unwrap();
    expect_event(&mut station, loco_event(22, state));
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn switches_functions_f0_to_f28() {
    let mut station = connect();
    let mut state = LocoState::default();
    for number in 0..=MAX_FUNCTION {
        state.set_function(number, true);
        station.set_loco(&dcc(23), &state).unwrap();
        expect_event(&mut station, loco_event(23, state));
    }
    state.set_function(5, false);
    station.set_loco(&dcc(23), &state).unwrap();
    expect_event(&mut station, loco_event(23, state));
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn stops_a_loco_in_an_emergency() {
    let mut station = connect();
    let state = LocoState {
        forward: true,
        step: 20,
        functions: 1,
    };
    station.set_loco(&dcc(24), &state).unwrap();
    expect_event(&mut station, loco_event(24, state));
    station.emergency_stop(&dcc(24), &state).unwrap();
    expect_event(&mut station, loco_event(24, LocoState { step: 0, ..state }));
}

#[test]
#[ignore = "needs srcpd: cargo xtask sim up"]
fn receives_changes_of_another_program() {
    let mut station = connect();
    let mut other = connect();
    for step in [5, 6] {
        let state = LocoState {
            forward: false,
            step,
            functions: 0b11,
        };
        other.set_loco(&dcc(25), &state).unwrap();
        expect_event(&mut station, loco_event(25, state));
    }
}
