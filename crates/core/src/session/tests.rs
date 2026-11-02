use super::*;
use serde_json::json;

fn session_with_loco() -> Session {
    let mut session = Session::default();
    session.apply(Command::AddLoco).unwrap();
    session
}

fn command(value: serde_json::Value) -> Command {
    serde_json::from_value(value).unwrap()
}

#[test]
fn add_loco_uses_the_defaults_of_electrip_1() {
    let session = session_with_loco();
    let entry = &session.locos()[0];
    assert_eq!(entry.id, 1);
    assert_eq!(
        *entry.loco.decoder(),
        Decoder::new(Protocol::DccShort, 1, 128).unwrap()
    );
    assert_eq!(entry.loco.max_speed(), 100.0);
    assert_eq!(
        entry.loco.speed_curve().points(),
        [(0.0, 0.0), (100.0, 128.0)]
    );
}

#[test]
fn ids_are_unique() {
    let mut session = session_with_loco();
    session.apply(Command::AddLoco).unwrap();
    let ids: Vec<u32> = session.locos().iter().map(|e| e.id).collect();
    assert_eq!(ids, [1, 2]);
}

#[test]
fn an_unknown_loco_is_an_error() {
    let mut session = session_with_loco();
    let error = session.apply(Command::SetAddress {
        loco: 7,
        address: 3,
    });
    assert_eq!(error, Err(CommandError::UnknownLoco(7)));
}

#[test]
fn a_failed_command_leaves_the_session_unchanged() {
    let mut session = session_with_loco();
    let before = session.clone();
    let error = session.apply(command(
        json!({"command": "set_max_speed", "loco": 1, "max_speed": 80.0}),
    ));
    assert_eq!(error, Err(CommandError::Loco(LocoError::ResetNotConfirmed)));
    assert_eq!(session, before);
}

#[test]
fn commands_are_read_from_json() {
    let mut session = session_with_loco();
    for value in [
        json!({"command": "set_protocol", "loco": 1, "protocol": "motorola2", "confirmed": true}),
        json!({"command": "set_speed_steps", "loco": 1, "speed_steps": 14, "confirmed": true}),
        json!({"command": "set_address", "loco": 1, "address": 42}),
        json!({"command": "add_curve_point", "loco": 1, "speed": 50.0, "step": 5.0}),
        json!({"command": "move_curve_point", "loco": 1, "point": 1, "speed": 60.0, "step": 6.0}),
        json!({"command": "add_curve_point", "loco": 1, "speed": 30.0, "step": 3.0}),
        json!({"command": "remove_curve_point", "loco": 1, "point": 2}),
    ] {
        session.apply(command(value)).unwrap();
    }
    let loco = &session.locos()[0].loco;
    assert_eq!(
        *loco.decoder(),
        Decoder::new(Protocol::Motorola2, 42, 14).unwrap()
    );
    assert_eq!(
        loco.speed_curve().points(),
        [(0.0, 0.0), (30.0, 3.0), (100.0, 14.0)]
    );
}

#[test]
fn the_state_is_written_as_json() {
    let session = session_with_loco();
    assert_eq!(
        serde_json::to_value(&session).unwrap(),
        json!({
            "locos": [{
                "id": 1,
                "decoder": {"protocol": "dcc_short", "address": 1, "speed_steps": 128},
                "max_speed": 100.0,
                "speed_curve": [[0.0, 0.0], [100.0, 128.0]]
            }],
            "station": "disconnected"
        })
    );
}

#[test]
fn errors_are_readable() {
    let error = CommandError::Loco(LocoError::MaxSpeedOutOfRange);
    assert_eq!(
        error.to_string(),
        "the maximum speed must be between 1 and 999 km/h"
    );
}
