//! The scenario suite of N-02, run against srcpd with a loopback bus and
//! against the Z21 simulator. The srcpd tests are `#[ignore]` since they need
//! srcpd on port 4303 (`cargo xtask sim up`); each uses its own loco
//! addresses, since they share the bus. An SRCP INFO session starts with the
//! current state, so each scenario first expects a state that differs from
//! the one it leaves behind.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use electrip_core::decoder::{Decoder, Protocol};
use electrip_core::station::{CommandStation, LocoState, MAX_FUNCTION, StationEvent};

/// Opens a new connection to the command station under test.
type Connect<'a> = &'a dyn Fn() -> Box<dyn CommandStation>;

fn dcc(address: u16) -> Decoder {
    Decoder::new(Protocol::DccShort, address, 28).unwrap()
}

fn expect(station: &mut dyn CommandStation, expected: StationEvent) {
    common::expect_event(station, |e| *e == expected);
}

fn loco_event(address: u16, state: LocoState) -> StationEvent {
    StationEvent::Loco { address, state }
}

fn connects_and_disconnects(connect: Connect) {
    let station = connect();
    drop(station);
    let mut station = connect();
    station.set_loco(&dcc(20), &LocoState::default()).unwrap();
}

fn switches_power(connect: Connect) {
    let mut station = connect();
    station.set_power(false).unwrap();
    expect(&mut *station, StationEvent::Power(false));
    station.set_power(true).unwrap();
    expect(&mut *station, StationEvent::Power(true));
}

fn drives_a_loco(connect: Connect) {
    let mut station = connect();
    for (forward, step) in [(true, 12), (false, 3)] {
        let state = LocoState {
            forward,
            step,
            functions: 0,
        };
        station.set_loco(&dcc(21), &state).unwrap();
        expect(&mut *station, loco_event(21, state));
    }
}

fn drives_a_loco_after_a_protocol_change(connect: Connect) {
    let mut station = connect();
    let state = LocoState {
        forward: true,
        step: 100,
        functions: 0,
    };
    let dcc128 = Decoder::new(Protocol::DccLong, 22, 128).unwrap();
    station.set_loco(&dcc128, &state).unwrap();
    expect(&mut *station, loco_event(22, state));
    let motorola = Decoder::new(Protocol::Motorola2, 22, 14).unwrap();
    let state = LocoState { step: 9, ..state };
    station.set_loco(&motorola, &state).unwrap();
    expect(&mut *station, loco_event(22, state));
}

fn switches_functions_f0_to_f28(connect: Connect) {
    let mut station = connect();
    let mut state = LocoState::default();
    for number in 0..=MAX_FUNCTION {
        state.set_function(number, true);
        station.set_loco(&dcc(23), &state).unwrap();
        expect(&mut *station, loco_event(23, state));
    }
    state.set_function(5, false);
    station.set_loco(&dcc(23), &state).unwrap();
    expect(&mut *station, loco_event(23, state));
}

fn stops_a_loco_in_an_emergency(connect: Connect) {
    let mut station = connect();
    let state = LocoState {
        forward: true,
        step: 20,
        functions: 1,
    };
    station.set_loco(&dcc(24), &state).unwrap();
    expect(&mut *station, loco_event(24, state));
    station.emergency_stop(&dcc(24), &state).unwrap();
    expect(
        &mut *station,
        loco_event(24, LocoState { step: 0, ..state }),
    );
}

fn receives_changes_of_another_program(connect: Connect) {
    let mut station = connect();
    let mut other = connect();
    for step in [5, 6] {
        let state = LocoState {
            forward: false,
            step,
            functions: 0b11,
        };
        other.set_loco(&dcc(25), &state).unwrap();
        expect(&mut *station, loco_event(25, state));
    }
}

/// The host takes a report that differs from what it sent for a change by
/// another program, so the top steps come back as sent.
fn reports_the_top_steps_as_sent(connect: Connect) {
    let mut station = connect();
    let dcc128 = Decoder::new(Protocol::DccLong, 26, 128).unwrap();
    for step in [128, 127, 126] {
        let state = LocoState {
            forward: true,
            step,
            functions: 0,
        };
        station.set_loco(&dcc128, &state).unwrap();
        expect(&mut *station, loco_event(26, state));
    }
}

mod srcpd {
    use super::*;
    use electrip_station_srcp::{DEFAULT_PORT, SrcpStation};

    const BUS: u16 = 1;

    fn connect() -> Box<dyn CommandStation> {
        Box::new(SrcpStation::connect("127.0.0.1", DEFAULT_PORT, BUS).unwrap())
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
    fn connects_and_disconnects() {
        super::connects_and_disconnects(&connect);
    }

    #[test]
    #[ignore = "needs srcpd: cargo xtask sim up"]
    fn switches_power() {
        super::switches_power(&connect);
    }

    #[test]
    #[ignore = "needs srcpd: cargo xtask sim up"]
    fn drives_a_loco() {
        super::drives_a_loco(&connect);
    }

    #[test]
    #[ignore = "needs srcpd: cargo xtask sim up"]
    fn drives_a_loco_after_a_protocol_change() {
        super::drives_a_loco_after_a_protocol_change(&connect);
    }

    #[test]
    #[ignore = "needs srcpd: cargo xtask sim up"]
    fn switches_functions_f0_to_f28() {
        super::switches_functions_f0_to_f28(&connect);
    }

    #[test]
    #[ignore = "needs srcpd: cargo xtask sim up"]
    fn stops_a_loco_in_an_emergency() {
        super::stops_a_loco_in_an_emergency(&connect);
    }

    #[test]
    #[ignore = "needs srcpd: cargo xtask sim up"]
    fn receives_changes_of_another_program() {
        super::receives_changes_of_another_program(&connect);
    }

    #[test]
    #[ignore = "needs srcpd: cargo xtask sim up"]
    fn reports_the_top_steps_as_sent() {
        super::reports_the_top_steps_as_sent(&connect);
    }
}

/// Each test starts its own simulator, so the tests share no state.
mod z21 {
    use super::*;
    use electrip_station_z21::Z21Station;

    /// Runs `scenario` against a new simulator.
    fn on_simulator(scenario: fn(Connect)) {
        let port = common::z21_simulator();
        scenario(&|| Box::new(Z21Station::connect("127.0.0.1", port).unwrap()));
    }

    #[test]
    fn connects_and_disconnects() {
        on_simulator(super::connects_and_disconnects);
    }

    #[test]
    fn switches_power() {
        on_simulator(super::switches_power);
    }

    #[test]
    fn drives_a_loco() {
        on_simulator(super::drives_a_loco);
    }

    #[test]
    fn drives_a_loco_after_a_protocol_change() {
        on_simulator(super::drives_a_loco_after_a_protocol_change);
    }

    #[test]
    fn switches_functions_f0_to_f28() {
        on_simulator(super::switches_functions_f0_to_f28);
    }

    #[test]
    fn stops_a_loco_in_an_emergency() {
        on_simulator(super::stops_a_loco_in_an_emergency);
    }

    #[test]
    fn receives_changes_of_another_program() {
        on_simulator(super::receives_changes_of_another_program);
    }

    #[test]
    fn reports_the_top_steps_as_sent() {
        on_simulator(super::reports_the_top_steps_as_sent);
    }
}
