//! What the window shows of the state of the host.

use crate::generated::{ButtonKind, ControlButton, Controller, MainWindow};
use serde::Deserialize;
use slint::{Image, Model, ModelRc, SharedString, VecModel};
use std::path::Path;

/// The part of the state the window shows; see `spec/steuerkanal.md`.
#[derive(Debug, Deserialize)]
pub struct State {
    locos: Vec<Loco>,
    devices: Vec<Device>,
    station: Station,
}

#[derive(Debug, Deserialize)]
struct Loco {
    id: i32,
    name: String,
    max_speed: f32,
    speed: f32,
    forward: bool,
    picture: Option<String>,
    sound_model: Option<serde_json::Value>,
    sound: String,
    sound_functions: Vec<Switch>,
    event_sounds: Vec<Switch>,
    functions: Vec<Switch>,
}

/// A function, sound function or event sound.
#[derive(Debug, Deserialize)]
struct Switch {
    action: i32,
    name: String,
    /// Only functions have a number.
    number: Option<u8>,
    /// Event sounds are `active` instead.
    #[serde(alias = "active")]
    on: bool,
}

#[derive(Debug, Deserialize)]
struct Device {
    loco: Option<i32>,
    color: i32,
}

#[derive(Debug, Deserialize)]
struct Station {
    connected: bool,
    track_power: bool,
}

pub fn show(window: &MainWindow, state: &State, media: &Path) {
    window.set_connected(state.station.connected);
    window.set_track_power(state.station.track_power);
    let controllers = controllers(state, media);
    let rows = controllers.iter().map(|c| c.buttons.row_count()).max();
    window.set_button_rows(rows.unwrap_or(0) as i32);
    let model = window.get_controllers();
    if let Some(model) = model.as_any().downcast_ref::<VecModel<Controller>>() {
        update(model, controllers);
    }
}

/// Changes only the rows that changed, so the buttons in the window stay
/// the same while the speed changes and a held button is released.
fn update(model: &VecModel<Controller>, rows: Vec<Controller>) {
    if model.row_count() != rows.len() {
        model.set_vec(rows);
        return;
    }
    for (index, mut row) in rows.into_iter().enumerate() {
        let Some(old) = model.row_data(index) else {
            continue;
        };
        if same(&old.buttons, &row.buttons) {
            row.buttons = old.buttons.clone();
        }
        if same(&old.devices, &row.devices) {
            row.devices = old.devices.clone();
        }
        if old != row {
            model.set_row_data(index, row);
        }
    }
}

fn same<T: PartialEq>(a: &ModelRc<T>, b: &ModelRc<T>) -> bool {
    a.iter().eq(b.iter())
}

pub(crate) fn controllers(state: &State, media: &Path) -> Vec<Controller> {
    state
        .locos
        .iter()
        .map(|l| controller(state, l, media))
        .collect()
}

fn controller(state: &State, loco: &Loco, media: &Path) -> Controller {
    let picture = loco
        .picture
        .as_ref()
        .and_then(|name| Image::load_from_path(&media.join(name)).ok());
    let devices: Vec<i32> = state
        .devices
        .iter()
        .filter(|d| d.loco == Some(loco.id))
        .map(|d| d.color)
        .collect();
    Controller {
        id: loco.id,
        name: loco.name.as_str().into(),
        has_picture: picture.is_some(),
        picture: picture.unwrap_or_default(),
        speed: loco.speed,
        max_speed: loco.max_speed,
        forward: loco.forward,
        buttons: ModelRc::new(VecModel::from(buttons(loco))),
        devices: ModelRc::new(VecModel::from(devices)),
    }
}

/// In the order of Electrip 1 (B-19): driving sound, sound functions, event
/// sounds, functions.
fn buttons(loco: &Loco) -> Vec<ControlButton> {
    let driving_sound = loco.sound_model.is_some().then(|| ControlButton {
        kind: ButtonKind::DrivingSound,
        label: SharedString::new(),
        on: loco.sound != "off",
        action: 0,
    });
    let groups = [
        (ButtonKind::SoundFunction, &loco.sound_functions),
        (ButtonKind::EventSound, &loco.event_sounds),
        (ButtonKind::Function, &loco.functions),
    ];
    let switches = groups.into_iter().flat_map(|(kind, switches)| {
        switches.iter().map(move |s| ControlButton {
            kind,
            label: label(s).into(),
            on: s.on,
            action: s.action,
        })
    });
    driving_sound.into_iter().chain(switches).collect()
}

/// A function without a name shows its number, like F1.
fn label(switch: &Switch) -> String {
    match switch.number {
        Some(number) if switch.name.is_empty() => format!("F{number}"),
        _ => switch.name.clone(),
    }
}

#[cfg(test)]
mod tests;
