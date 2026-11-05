use super::*;
use crate::sound::{Engine, EngineSound, SegmentSound};
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

/// Every value Electrip 2 knows yet arrives unchanged, except a function
/// on the button of a built-in action (Q-015).
#[test]
fn the_corpus_is_imported_without_loss() {
    let reports: [(&str, &[&str]); 3] = [
        ("empty", &[]),
        ("packages", &[]),
        (
            "settings",
            &[
                "button 8: functions left out, it is Reverse",
                "button 6: functions left out, it is ToggleSound",
            ],
        ),
    ];
    for (name, report) in reports {
        let path = corpus(name);
        let file: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        let import = read(&path).unwrap();
        assert_eq!(import.report, report, "{name}");
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
            assert_sounds(loco, &old["engine"]);
        }
        assert_mapping(&import, &file["joystick"]);
    }
}

/// The engine, its sounds, its segments and how a steam engine strokes
/// arrive.
fn assert_sounds(loco: &Loco, old: &Value) {
    let Some(model) = loco.sound_model() else {
        assert!(old.is_null());
        return;
    };
    let path = |sound: Option<&Path>| sound.map(|p| p.to_str().unwrap().to_string());
    assert_eq!(serde_json::to_value(model.engine()).unwrap(), old["type"]);
    for (sound, key) in [
        (EngineSound::Start, "start_sound"),
        (EngineSound::Idle, "idle_sound"),
        (EngineSound::Quit, "quit_sound"),
        (EngineSound::Cylinder, "cylinder_steam_sound"),
    ] {
        assert_eq!(path(model.sound(sound)).as_deref(), old[key].as_str());
    }
    if model.engine() == Engine::Steam {
        let steam = model.steam();
        assert_eq!(steam.strokes, old["nr_strokes"]);
        assert_eq!(steam.wheel_diameter, old["wheel_diameter"]);
        assert_eq!(steam.start_delay, old["stroke_start_delay"]);
        assert_eq!(steam.min_frequency, old["min_freq"]);
    }
    let segments = old["sound_segments"].as_array().unwrap();
    assert_eq!(model.segments().len(), segments.len());
    for (nr, (segment, old)) in model.segments().iter().zip(segments).enumerate() {
        assert_eq!(segment.start, old["start"]);
        for (sound, key) in [
            (SegmentSound::Load, "load_sound"),
            (SegmentSound::Idle, "idle_sound"),
            (SegmentSound::Accel, "accel_sound"),
            (SegmentSound::Decel, "decel_sound"),
        ] {
            let sound = path(model.segment_sound(nr, sound));
            assert_eq!(sound.as_deref(), old[key].as_str());
        }
        let strokes = old["stroke_sounds"].as_array().cloned().unwrap_or_default();
        for (stroke, old) in strokes.iter().enumerate() {
            let sound = path(model.stroke_sound(nr, stroke));
            assert_eq!(sound.as_deref(), old.as_str());
        }
    }
}

/// The joystick settings and each button of a function are in the mapping
/// of the device type "Electrip 1".
fn assert_mapping(import: &Import, joystick: &Value) {
    let mapping = &import.mapping;
    assert_eq!(mapping.kind, KIND);
    let button = |key: &str| format!("button{}", joystick[key]);
    assert_eq!(
        mapping.target(&format!("axis{}", joystick["accel_axis"])),
        Some(&Target::Drive {
            dead_zone: joystick["axis_threshold"].as_f64().unwrap()
        })
    );
    let built_in = [
        ("emergency_button", Target::TogglePower),
        ("reverse_button", Target::Reverse),
        ("focus_button", Target::Focus),
        ("sound_button", Target::ToggleSound),
    ];
    for (key, target) in &built_in {
        assert_eq!(mapping.target(&button(key)), Some(target));
    }
    let mut buttons = Vec::new();
    for action in &import.actions {
        if let Some(number) = action.name.strip_prefix("Knopf ") {
            let control = format!("button{number}");
            if built_in.iter().any(|(key, _)| button(key) == control) {
                continue;
            }
            let target = Target::Action { action: action.id };
            assert_eq!(mapping.target(&control), Some(&target));
            buttons.push(control);
        }
    }
    let built_in = built_in.iter().map(|(key, _)| button(key));
    buttons.extend(built_in);
    buttons.sort();
    buttons.dedup();
    assert_eq!(mapping.bindings.len(), buttons.len() + 1);
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
        let mode = if matches!(old["toggle_mode"].as_i64(), Some(1 | 2)) {
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
fn built_in_actions_take_the_button_of_a_function() {
    let file = json!({"locos": [{"speed_control_points": [[0, 0], [100, 128]], "functions": [
        {"name": "Licht", "nr": 0, "button": 1},
        {"name": "Horn", "nr": 1, "button": 2},
    ]}], "server": {}, "joystick": {"sound_button": -1, "accel_axis": 0, "axis_threshold": 0.2}});
    let import = import_value(file).unwrap();
    let bindings: Vec<_> = import
        .mapping
        .bindings
        .iter()
        .map(|b| (b.control.as_str(), b.target.clone()))
        .collect();
    assert_eq!(
        bindings,
        [
            ("button2", Target::Action { action: 2 }),
            ("button0", Target::TogglePower),
            ("button1", Target::Reverse),
            ("button3", Target::Focus),
            ("axis0", Target::Drive { dead_zone: 0.2 }),
        ]
    );
    assert_eq!(
        import.report,
        ["button 1: functions left out, it is Reverse"]
    );
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
    let mapping = &import.mapping;
    assert_eq!(
        mapping.target("axis2"),
        Some(&Target::Drive { dead_zone: 0.06 })
    );
    assert_eq!(mapping.target("button0"), Some(&Target::TogglePower));
    assert_eq!(mapping.target("button4"), Some(&Target::ToggleSound));
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
