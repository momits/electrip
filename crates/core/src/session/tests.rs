use super::*;
use serde_json::{Value, json};

fn session_with_loco() -> Session {
    session_with_locos(1)
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
    assert_eq!(entry.loco.accel_duration(), 11.5);
    assert_eq!(entry.loco.brake_duration(), 8.5);
    assert_eq!(entry.loco.volume(), 0.8);
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
        json!({"command": "set_accel_duration", "loco": 1, "seconds": 20.0}),
        json!({"command": "set_brake_duration", "loco": 1, "seconds": 4.5}),
        json!({"command": "set_volume", "loco": 1, "volume": 0.25}),
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
    assert_eq!(
        (loco.accel_duration(), loco.brake_duration(), loco.volume()),
        (20.0, 4.5, 0.25)
    );
}

#[test]
fn the_state_is_written_as_json() {
    let mut session = session_with_loco();
    session
        .apply(Command::AddAction {
            name: "Licht".into(),
        })
        .unwrap();
    add_function(&mut session, 1, 1, 0);
    session
        .apply(command(
            json!({"command": "add_device", "device": 7, "kind": "Xbox"}),
        ))
        .unwrap();
    session
        .apply(command(json!({"command": "bind", "kind": "Xbox", "control": "lefty", "target": {"type": "action", "action": 1}})))
        .unwrap();
    session
        .apply(command(
            json!({"command": "unbind", "kind": "Xbox", "control": "a"}),
        ))
        .unwrap();
    assert_eq!(
        serde_json::to_value(&session).unwrap(),
        json!({
            "locos": [{
                "id": 1,
                "name": "Unbenannte Lok",
                "decoder": {"protocol": "dcc_short", "address": 1, "speed_steps": 128},
                "max_speed": 100.0,
                "speed_curve": [[0.0, 0.0], [100.0, 128.0]],
                "accel_duration": 11.5,
                "brake_duration": 8.5,
                "volume": 0.8,
                "functions": [{"action": 1, "number": 0, "name": "Licht", "mode": "switch", "default_on": false, "on": false}],
                "picture": null,
                "speed": 0.0,
                "forward": true
            }],
            "actions": [{"id": 1, "name": "Licht"}],
            "mappings": [{"kind": "Xbox", "bindings": [
                {"control": "b", "target": {"type": "reverse"}},
                {"control": "dpleft", "target": {"type": "previous_loco"}},
                {"control": "dpright", "target": {"type": "next_loco"}},
                {"control": "lefty", "target": {"type": "action", "action": 1}}
            ]}],
            "devices": [{"id": 7, "kind": "Xbox", "loco": 1}],
            "station": {"host": "localhost", "port": 4303, "bus": 1, "power_on_start": true, "connected": false, "track_power": false},
            "import_report": [],
            "configuration": "",
            "configurations": []
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

fn session_with_locos(count: usize) -> Session {
    let mut session = Session::default();
    for _ in 0..count {
        session.apply(Command::AddLoco).unwrap();
    }
    session
}

fn ids(session: &Session) -> Vec<u32> {
    session.locos().iter().map(|e| e.id).collect()
}

#[test]
fn a_new_loco_is_unnamed() {
    let session = session_with_loco();
    assert_eq!(session.locos()[0].loco.name(), "Unbenannte Lok");
}

#[test]
fn rename_loco_sets_the_name() {
    let mut session = session_with_loco();
    let rename = command(json!({"command": "rename_loco", "loco": 1, "name": "BR 218"}));
    session.apply(rename).unwrap();
    assert_eq!(session.locos()[0].loco.name(), "BR 218");
}

#[test]
fn remove_loco_removes_only_that_loco() {
    let mut session = session_with_locos(3);
    session
        .apply(command(json!({"command": "remove_loco", "loco": 2})))
        .unwrap();
    assert_eq!(ids(&session), [1, 3]);
    assert_eq!(
        session.apply(Command::RemoveLoco { loco: 2 }),
        Err(CommandError::UnknownLoco(2))
    );
}

#[test]
fn ids_of_removed_locos_are_not_reused() {
    let mut session = session_with_locos(2);
    session.apply(Command::RemoveLoco { loco: 2 }).unwrap();
    session.apply(Command::AddLoco).unwrap();
    assert_eq!(ids(&session), [1, 3]);
}

#[test]
fn move_loco_changes_the_order() {
    let mut session = session_with_locos(3);
    session
        .apply(command(
            json!({"command": "move_loco", "loco": 3, "position": 0}),
        ))
        .unwrap();
    assert_eq!(ids(&session), [3, 1, 2]);
    session
        .apply(Command::MoveLoco {
            loco: 3,
            position: 2,
        })
        .unwrap();
    assert_eq!(ids(&session), [1, 2, 3]);
}

#[test]
fn move_loco_fails_for_a_position_outside_the_list() {
    let mut session = session_with_locos(2);
    let error = session.apply(Command::MoveLoco {
        loco: 1,
        position: 2,
    });
    assert_eq!(error, Err(CommandError::PositionOutOfRange(2)));
    assert_eq!(ids(&session), [1, 2]);
}

/// A session with two locos and the actions "Licht" (1) and "Horn" (2).
fn session_with_actions() -> Session {
    let mut session = session_with_locos(2);
    for name in ["Licht", "Horn"] {
        session
            .apply(Command::AddAction { name: name.into() })
            .unwrap();
    }
    session
}

fn try_add_function(session: &mut Session, loco: u32, function: Value) -> Result<(), CommandError> {
    session.apply(command(
        json!({"command": "add_function", "loco": loco, "function": function}),
    ))
}

fn add_function(session: &mut Session, loco: u32, action: u32, number: u8) {
    let function = json!({"action": action, "number": number, "name": "Licht"});
    try_add_function(session, loco, function).unwrap();
}

fn trigger(session: &mut Session, loco: u32, action: u32, pressed: bool) {
    session
        .apply(Command::TriggerAction {
            loco,
            action,
            pressed,
        })
        .unwrap();
}

fn station_functions(session: &Session, loco: usize) -> u32 {
    session.locos()[loco].station_state().functions
}

#[test]
fn actions_are_added_renamed_and_removed() {
    let mut session = session_with_actions();
    session
        .apply(Command::RenameAction {
            action: 1,
            name: "Fernlicht".into(),
        })
        .unwrap();
    session.apply(Command::RemoveAction { action: 2 }).unwrap();
    session
        .apply(Command::AddAction {
            name: "Pfiff".into(),
        })
        .unwrap();
    let actions: Vec<(u32, &str)> = session
        .actions()
        .iter()
        .map(|a| (a.id, a.name.as_str()))
        .collect();
    assert_eq!(actions, [(1, "Fernlicht"), (3, "Pfiff")]);
}

#[test]
fn an_unknown_action_is_an_error() {
    let mut session = session_with_actions();
    let error = session.apply(Command::RemoveAction { action: 7 });
    assert_eq!(error, Err(CommandError::UnknownAction(7)));
    let error = try_add_function(&mut session, 1, json!({"action": 7, "number": 0}));
    assert_eq!(error, Err(CommandError::UnknownAction(7)));
}

#[test]
fn a_function_above_f28_is_an_error() {
    let mut session = session_with_actions();
    let error = try_add_function(&mut session, 1, json!({"action": 1, "number": 29}));
    assert_eq!(error, Err(CommandError::FunctionOutOfRange(29)));
}

#[test]
fn an_action_switches_different_functions_at_different_locos() {
    let mut session = session_with_actions();
    add_function(&mut session, 1, 1, 0);
    add_function(&mut session, 2, 1, 4);
    trigger(&mut session, 1, 1, true);
    trigger(&mut session, 2, 1, true);
    assert_eq!(station_functions(&session, 0), 1 << 0);
    assert_eq!(station_functions(&session, 1), 1 << 4);
}

#[test]
fn an_action_affects_only_the_given_loco() {
    let mut session = session_with_actions();
    add_function(&mut session, 1, 1, 0);
    add_function(&mut session, 2, 1, 0);
    trigger(&mut session, 1, 1, true);
    assert_eq!(station_functions(&session, 1), 0);
}

#[test]
fn an_action_without_a_function_at_the_loco_does_nothing() {
    let mut session = session_with_actions();
    add_function(&mut session, 1, 1, 0);
    let before = session.clone();
    trigger(&mut session, 1, 2, true);
    assert_eq!(session, before);
}

#[test]
fn a_function_starts_in_its_default_state() {
    let mut session = session_with_actions();
    let function = json!({"action": 1, "number": 2, "mode": "push", "default_on": true});
    try_add_function(&mut session, 1, function).unwrap();
    assert_eq!(station_functions(&session, 0), 1 << 2);
    trigger(&mut session, 1, 1, true);
    assert_eq!(station_functions(&session, 0), 0);
}

fn function_numbers(session: &Session) -> Vec<u8> {
    let functions = session.locos()[0].loco.functions();
    functions.iter().map(|f| f.number).collect()
}

#[test]
fn functions_are_removed_and_moved() {
    let mut session = session_with_actions();
    for number in [0, 1, 2] {
        add_function(&mut session, 1, 1, number);
    }
    session
        .apply(Command::MoveFunction {
            loco: 1,
            index: 0,
            position: 2,
        })
        .unwrap();
    assert_eq!(function_numbers(&session), [1, 2, 0]);
    session
        .apply(Command::RemoveFunction { loco: 1, index: 1 })
        .unwrap();
    assert_eq!(function_numbers(&session), [1, 0]);
    let error = session.apply(Command::RemoveFunction { loco: 1, index: 2 });
    assert_eq!(error, Err(CommandError::PositionOutOfRange(2)));
}

#[test]
fn removing_an_action_removes_its_functions() {
    let mut session = session_with_actions();
    add_function(&mut session, 1, 1, 0);
    add_function(&mut session, 1, 2, 1);
    add_function(&mut session, 2, 1, 0);
    session.apply(Command::RemoveAction { action: 1 }).unwrap();
    assert_eq!(function_numbers(&session), [1]);
    assert!(session.locos()[1].loco.functions().is_empty());
}
