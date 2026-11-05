//! Import of the configuration files of Electrip 1 (B-21). Missing values of
//! a loco or the server get the defaults of Electrip 1; a missing loco list,
//! server or speed curve makes the file invalid, as in Electrip 1.
//!
//! Electrip 1 allowed DCC short addresses up to 10239. Such locos become DCC
//! long and are named in the report (B-06).
//!
//! Each button number that a function uses becomes a logical action
//! "Knopf <n>" (ADR 0009); a function without a button gets an action with
//! its own name. The buttons and the drive axis of `joystick` become the
//! mapping of the device type "Electrip 1" (Q-014); a button that is both a
//! built-in action and a function stays the built-in action.

use crate::decoder::{Decoder, Protocol};
use crate::function::{Action, Function, Mode};
use crate::input::{Mapping, Target};
use crate::loco::{DEFAULT_NAME, Loco, LocoError};
use crate::session::Station;
use crate::sound::{Engine, EngineSound, Segment, SegmentSound, SoundModel, Sounds};
use crate::speed_curve::{Point, SpeedCurve};
use crate::station::MAX_FUNCTION;
use serde::Deserialize;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

/// The device type of the mapping from a file of Electrip 1.
pub const KIND: &str = "Electrip 1";

/// What a file of Electrip 1 holds, as far as Electrip 2 knows it yet.
#[derive(Debug, Clone, PartialEq)]
pub struct Import {
    pub locos: Vec<Loco>,
    /// The actions the functions of the locos use.
    pub actions: Vec<Action>,
    pub station: Station,
    pub mapping: Mapping,
    /// The image file of each loco, if it has one (B-05).
    pub pictures: Vec<Option<PathBuf>>,
    /// Changes made to fit the file to Electrip 2, one line each.
    pub report: Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ImportError {
    Read(String),
    Invalid(String),
    UnknownProtocol { loco: String, protocol: String },
    InvalidSpeedCurve { loco: String },
    Loco { loco: String, error: LocoError },
}

impl fmt::Display for ImportError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            ImportError::Read(reason) => write!(f, "cannot read the file: {reason}"),
            ImportError::Invalid(reason) => write!(f, "invalid file: {reason}"),
            ImportError::UnknownProtocol { loco, protocol } => {
                write!(f, "{loco}: unknown protocol {protocol:?}")
            }
            ImportError::InvalidSpeedCurve { loco } => write!(f, "{loco}: invalid speed curve"),
            ImportError::Loco { loco, error } => write!(f, "{loco}: {error}"),
        }
    }
}

#[derive(Deserialize)]
struct File {
    locos: Vec<OldLoco>,
    server: Station,
    #[serde(default)]
    joystick: Joystick,
}

/// Button and axis numbers of pygame; -1 is no button.
#[derive(Deserialize)]
#[serde(default)]
struct Joystick {
    emergency_button: i32,
    reverse_button: i32,
    accel_axis: i32,
    axis_threshold: f64,
    focus_button: i32,
    sound_button: i32,
}

impl Default for Joystick {
    fn default() -> Self {
        Joystick {
            emergency_button: 0,
            reverse_button: 1,
            accel_axis: 2,
            axis_threshold: 0.06,
            focus_button: 3,
            sound_button: 4,
        }
    }
}

#[derive(Deserialize)]
#[serde(default)]
struct OldLoco {
    name: String,
    speed_steps: u8,
    max_speed: f64,
    address: u16,
    protocol: String,
    accel_duration: f64,
    decel_duration: f64,
    sound_volume: f64,
    speed_control_points: Vec<Point>,
    img_path: Option<PathBuf>,
    functions: Vec<OldFunction>,
    engine: Option<OldEngine>,
}

/// The sound of a loco. Steam engines keep only their idle sound and their
/// segments for now (B-14).
#[derive(Deserialize)]
struct OldEngine {
    #[serde(rename = "type")]
    engine: Engine,
    start_sound: Option<PathBuf>,
    idle_sound: Option<PathBuf>,
    quit_sound: Option<PathBuf>,
    /// `null` without segments.
    #[serde(default)]
    sound_segments: Option<Vec<OldSegment>>,
}

/// A sound segment; its end is the start of the next one.
#[derive(Deserialize)]
struct OldSegment {
    start: f64,
    load_sound: Option<PathBuf>,
    idle_sound: Option<PathBuf>,
    accel_sound: Option<PathBuf>,
    decel_sound: Option<PathBuf>,
}

/// A decoder function; `button` is -1 without a button.
#[derive(Default, Deserialize)]
#[serde(default)]
struct OldFunction {
    name: String,
    nr: u8,
    state: bool,
    button: i32,
    toggle_mode: u8,
}

/// Defaults of Electrip 1 (`legacy/src/electrip/config/json_model.py`).
impl Default for OldLoco {
    fn default() -> Self {
        OldLoco {
            name: DEFAULT_NAME.into(),
            speed_steps: 128,
            max_speed: 100.0,
            address: 1,
            protocol: "N 1".into(),
            accel_duration: 11.5,
            decel_duration: 8.5,
            sound_volume: 0.0,
            speed_control_points: Vec::new(),
            img_path: None,
            functions: Vec::new(),
            engine: None,
        }
    }
}

/// Reads a file of Electrip 1.
pub fn read(path: &Path) -> Result<Import, ImportError> {
    let json = fs::read_to_string(path).map_err(|e| ImportError::Read(e.to_string()))?;
    import(&json)
}

/// Reads the content of a file of Electrip 1.
fn import(json: &str) -> Result<Import, ImportError> {
    let file: File = serde_json::from_str(json).map_err(|e| ImportError::Invalid(e.to_string()))?;
    let mut report = Vec::new();
    let mut actions = Vec::new();
    let pictures = file.locos.iter().map(|old| old.img_path.clone()).collect();
    let buttons: Vec<i32> = file
        .locos
        .iter()
        .flat_map(|old| &old.functions)
        .map(|f| f.button)
        .collect();
    let locos = file
        .locos
        .into_iter()
        .map(|old| convert(old, &mut actions, &mut report))
        .collect::<Result<Vec<_>, _>>()?;
    let mapping = mapping(&file.joystick, &buttons, &actions, &mut report);
    Ok(Import {
        locos,
        actions,
        station: file.server,
        mapping,
        pictures,
        report,
    })
}

/// Reads the loco file of a loco package of Electrip 1 (B-20); returns the
/// loco, the actions its functions use and the path of its image file in
/// the package.
pub fn loco(
    json: &[u8],
    report: &mut Vec<String>,
) -> Result<(Loco, Vec<Action>, Option<PathBuf>), ImportError> {
    let old: OldLoco =
        serde_json::from_slice(json).map_err(|e| ImportError::Invalid(e.to_string()))?;
    let picture = old.img_path.clone();
    let mut actions = Vec::new();
    let loco = convert(old, &mut actions, report)?;
    Ok((loco, actions, picture))
}

fn convert(
    old: OldLoco,
    actions: &mut Vec<Action>,
    report: &mut Vec<String>,
) -> Result<Loco, ImportError> {
    let mut protocol = protocol(&old)?;
    if protocol == Protocol::DccShort && old.address > protocol.max_address() {
        protocol = Protocol::DccLong;
        report.push(format!(
            "{}: address {} is too high for DCC short, changed to DCC long",
            old.name, old.address
        ));
    }
    let loco_error = |error: LocoError| ImportError::Loco {
        loco: old.name.clone(),
        error,
    };
    let decoder =
        Decoder::new(protocol, old.address, old.speed_steps).map_err(|e| loco_error(e.into()))?;
    let mut loco = Loco::new(decoder, old.max_speed).map_err(loco_error)?;
    loco.set_accel_duration(old.accel_duration)
        .map_err(loco_error)?;
    loco.set_brake_duration(old.decel_duration)
        .map_err(loco_error)?;
    loco.set_volume(old.sound_volume).map_err(loco_error)?;
    *loco.speed_curve_mut() =
        SpeedCurve::new(&old.speed_control_points).ok_or(ImportError::InvalidSpeedCurve {
            loco: old.name.clone(),
        })?;
    *loco.functions_mut() = old
        .functions
        .into_iter()
        .filter_map(|f| function(f, &old.name, actions, report))
        .collect();
    loco.set_sound_model(old.engine.map(sound_model));
    loco.set_name(old.name);
    Ok(loco)
}

fn sound_model(old: OldEngine) -> SoundModel {
    let segments = old.sound_segments.unwrap_or_default();
    let segments = segments.into_iter().map(|s| Segment {
        start: s.start,
        sounds: sounds([
            (SegmentSound::Load, s.load_sound),
            (SegmentSound::Idle, s.idle_sound),
            (SegmentSound::Accel, s.accel_sound),
            (SegmentSound::Decel, s.decel_sound),
        ]),
    });
    let engine_sounds = sounds([
        (EngineSound::Start, old.start_sound),
        (EngineSound::Idle, old.idle_sound),
        (EngineSound::Quit, old.quit_sound),
    ]);
    SoundModel::with(old.engine, engine_sounds, segments.collect())
}

/// The sounds that are set.
fn sounds<K: Ord, const N: usize>(sounds: [(K, Option<PathBuf>); N]) -> Sounds<K> {
    sounds
        .into_iter()
        .filter_map(|(kind, path)| Some((kind, path?)))
        .collect()
}

/// Functions above F28 are left out and named in the report. Push and
/// "push limited" are push buttons; the other modes switch.
fn function(
    old: OldFunction,
    loco: &str,
    actions: &mut Vec<Action>,
    report: &mut Vec<String>,
) -> Option<Function> {
    if old.nr > MAX_FUNCTION {
        report.push(format!("{loco}: function F{} left out", old.nr));
        return None;
    }
    let name = match old.button {
        ..0 => old.name.clone(),
        button => button_action(button),
    };
    Some(Function {
        action: action_id(actions, name),
        number: old.nr,
        name: old.name,
        mode: if matches!(old.toggle_mode, 1 | 2) {
            Mode::Push
        } else {
            Mode::Switch
        },
        default_on: old.state,
        on: old.state,
    })
}

/// Binds each button that has an action to it, then the built-in actions;
/// a function whose button they take is named in the report. Functions
/// that `function` left out have no action.
fn mapping(
    joystick: &Joystick,
    buttons: &[i32],
    actions: &[Action],
    report: &mut Vec<String>,
) -> Mapping {
    let mut mapping = Mapping {
        kind: KIND.into(),
        bindings: Vec::new(),
    };
    for button in buttons {
        let name = button_action(*button);
        if let Some(action) = actions.iter().find(|a| a.name == name) {
            let target = Target::Action { action: action.id };
            mapping.bind(format!("button{button}"), target);
        }
    }
    let built_in = [
        (joystick.emergency_button, Target::TogglePower),
        (joystick.reverse_button, Target::Reverse),
        (joystick.focus_button, Target::Focus),
        (joystick.sound_button, Target::ToggleSound),
    ];
    for (button, target) in built_in.into_iter().filter(|(b, _)| *b >= 0) {
        let control = format!("button{button}");
        if mapping.target(&control).is_some() {
            report.push(format!(
                "button {button}: functions left out, it is {target:?}"
            ));
        }
        mapping.bind(control, target);
    }
    if joystick.accel_axis >= 0 {
        let target = Target::Drive {
            dead_zone: joystick.axis_threshold,
        };
        mapping.bind(format!("axis{}", joystick.accel_axis), target);
    }
    mapping
}

/// The name of the action of a button.
fn button_action(button: i32) -> String {
    format!("Knopf {button}")
}

/// The id of the action `name`; adds it if missing.
fn action_id(actions: &mut Vec<Action>, name: String) -> u32 {
    if let Some(action) = actions.iter().find(|a| a.name == name) {
        return action.id;
    }
    let id = actions.len() as u32 + 1;
    actions.push(Action { id, name });
    id
}

fn protocol(old: &OldLoco) -> Result<Protocol, ImportError> {
    match old.protocol.as_str() {
        "M 1" => Ok(Protocol::Motorola1),
        "M 2" => Ok(Protocol::Motorola2),
        "N 1" => Ok(Protocol::DccShort),
        "N 2" => Ok(Protocol::DccLong),
        other => Err(ImportError::UnknownProtocol {
            loco: old.name.clone(),
            protocol: other.into(),
        }),
    }
}

#[cfg(test)]
mod tests;
