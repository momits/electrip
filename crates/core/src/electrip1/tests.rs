use super::*;
use serde_json::{Value, json};
use std::path::PathBuf;

fn corpus(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("../../tests/corpus/configs/{name}.json"))
}

fn import_value(file: Value) -> Result<Import, ImportError> {
    import(&file.to_string())
}

fn file_with_loco(loco: Value) -> Value {
    json!({"locos": [loco], "server": {}})
}

fn protocol_name(protocol: Protocol) -> &'static str {
    match protocol {
        Protocol::Motorola1 => "M 1",
        Protocol::Motorola2 => "M 2",
        Protocol::DccShort => "N 1",
        Protocol::DccLong => "N 2",
    }
}

/// Every value Electrip 2 knows yet arrives unchanged.
#[test]
fn the_corpus_is_imported_without_loss() {
    for name in ["empty", "packages", "settings"] {
        let path = corpus(name);
        let file: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        let import = read(&path).unwrap();
        assert!(import.report.is_empty(), "{name}");
        let server = &file["server"];
        assert_eq!(import.station.host, server["host"], "{name}");
        assert_eq!(import.station.port, server["port"], "{name}");
        assert_eq!(import.station.bus, server["bus"], "{name}");
        assert_eq!(import.station.power_on_start, server["power"], "{name}");
        let old_locos = file["locos"].as_array().unwrap();
        assert_eq!(import.locos.len(), old_locos.len(), "{name}");
        for ((loco, picture), old) in import.locos.iter().zip(&import.pictures).zip(old_locos) {
            assert_eq!(
                picture.as_deref().and_then(Path::to_str),
                old["img_path"].as_str()
            );
            let decoder = loco.decoder();
            assert_eq!(loco.name(), old["name"]);
            assert_eq!(protocol_name(decoder.protocol()), old["protocol"]);
            assert_eq!(decoder.address(), old["address"]);
            assert_eq!(decoder.speed_steps(), old["speed_steps"]);
            assert_eq!(loco.max_speed(), old["max_speed"]);
            assert_eq!(loco.accel_duration(), old["accel_duration"]);
            assert_eq!(loco.brake_duration(), old["decel_duration"]);
            assert_eq!(loco.volume(), old["sound_volume"]);
            let points: Vec<Point> =
                serde_json::from_value(old["speed_control_points"].clone()).unwrap();
            assert_eq!(loco.speed_curve().points(), points);
            assert_functions(loco, &import.actions, &old["functions"]);
        }
    }
}

/// Each function keeps name, number, state and mode, and its action names
/// the button or, without one, the function.
fn assert_functions(loco: &Loco, actions: &[Action], old: &Value) {
    let old = old.as_array().unwrap();
    assert_eq!(loco.functions().len(), old.len());
    for (function, old) in loco.functions().iter().zip(old) {
        assert_eq!(function.name, old["name"]);
        assert_eq!(function.number, old["nr"]);
        assert_eq!(function.default_on, old["state"]);
        assert_eq!(function.on, old["state"]);
        let mode = if old["toggle_mode"] == 1 {
            Mode::Push
        } else {
            Mode::Switch
        };
        assert_eq!(function.mode, mode);
        let action = actions.iter().find(|a| a.id == function.action).unwrap();
        let button = old["button"].as_i64().unwrap();
        let name = if button < 0 {
            old["name"].as_str().unwrap().to_string()
        } else {
            format!("Knopf {button}")
        };
        assert_eq!(action.name, name);
    }
}

#[test]
fn locos_share_the_action_of_a_button() {
    let curve = json!([[0, 0], [100, 128]]);
    let file = json!({"locos": [
        {"name": "A", "speed_control_points": curve, "functions": [
            {"name": "Licht", "nr": 0, "button": 6},
            {"name": "Horn", "nr": 2, "button": -1, "toggle_mode": 1},
        ]},
        {"name": "B", "speed_control_points": curve, "functions": [
            {"name": "Pfeife", "nr": 1, "button": 6, "toggle_mode": 2},
            {"name": "Rauch", "nr": 29, "button": 7},
        ]},
    ], "server": {}});
    let import = import_value(file).unwrap();
    let names: Vec<_> = import.actions.iter().map(|a| a.name.as_str()).collect();
    assert_eq!(names, ["Knopf 6", "Horn"]);
    let functions = |i: usize| -> Vec<_> {
        import.locos[i]
            .functions()
            .iter()
            .map(|f| (f.action, f.mode))
            .collect()
    };
    assert_eq!(functions(0), [(1, Mode::Switch), (2, Mode::Push)]);
    assert_eq!(functions(1), [(1, Mode::Push)]);
    assert_eq!(import.report, ["B: function F29 left out"]);
}

#[test]
fn missing_values_get_the_defaults_of_electrip_1() {
    let file = json!({"locos": [{"speed_control_points": [[0, 0], [100, 128]]}], "server": {}});
    let import = import_value(file).unwrap();
    let loco = &import.locos[0];
    assert_eq!(loco.name(), DEFAULT_NAME);
    assert_eq!(
        *loco.decoder(),
        Decoder::new(Protocol::DccShort, 1, 128).unwrap()
    );
    assert_eq!(loco.max_speed(), 100.0);
    assert_eq!(loco.accel_duration(), 11.5);
    assert_eq!(loco.brake_duration(), 8.5);
    assert_eq!(loco.volume(), 0.0);
    assert_eq!(import.station, Station::default());
}

#[test]
fn a_dcc_short_address_above_127_becomes_dcc_long() {
    let file = file_with_loco(json!({
        "name": "V 100", "protocol": "N 1", "address": 200,
        "speed_control_points": [[0, 0], [100, 128]]
    }));
    let import = import_value(file).unwrap();
    assert_eq!(
        *import.locos[0].decoder(),
        Decoder::new(Protocol::DccLong, 200, 128).unwrap()
    );
    assert_eq!(
        import.report,
        ["V 100: address 200 is too high for DCC short, changed to DCC long"]
    );
}

#[test]
fn inner_curve_points_are_kept() {
    let file = file_with_loco(json!({"speed_control_points": [[0, 0], [30, 50], [100, 128]]}));
    let import = import_value(file).unwrap();
    assert_eq!(
        import.locos[0].speed_curve().points(),
        [(0.0, 0.0), (30.0, 50.0), (100.0, 128.0)]
    );
}

#[test]
fn invalid_files_are_errors() {
    let curve = json!([[0, 0], [100, 128]]);
    let cases = [
        (
            json!({"server": {}}),
            "invalid file: missing field `locos` at line 1 column 13",
        ),
        (
            json!({"locos": []}),
            "invalid file: missing field `server` at line 1 column 12",
        ),
        (
            file_with_loco(json!({"name": "A", "protocol": "X", "speed_control_points": curve})),
            "A: unknown protocol \"X\"",
        ),
        (
            file_with_loco(json!({"name": "B"})),
            "B: invalid speed curve",
        ),
        (
            file_with_loco(
                json!({"name": "C", "protocol": "M 1", "address": 81, "speed_steps": 14, "speed_control_points": curve}),
            ),
            "C: the address must be between 1 and 80",
        ),
        (
            file_with_loco(json!({"name": "D", "sound_volume": 2, "speed_control_points": curve})),
            "D: the volume must be between 0 and 1",
        ),
    ];
    for (file, error) in cases {
        assert_eq!(import_value(file).unwrap_err().to_string(), error);
    }
}

#[test]
fn a_missing_file_is_an_error() {
    let error = read(Path::new("/nonexistent/electrip.json")).unwrap_err();
    assert!(matches!(error, ImportError::Read(_)));
}
