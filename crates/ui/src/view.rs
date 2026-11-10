//! What the window shows of the state of the host.

use crate::generated::{AudioTarget, ButtonKind, ControlButton, Controller, MainWindow};
use electrip_core::picture;
use serde::Deserialize;
use serde::de::IgnoredAny;
use slint::{Image, Model, ModelRc, SharedString, VecModel};
use std::collections::BTreeMap;
use std::path::Path;

/// The part of the state the window shows; see `spec/steuerkanal.md`.
#[derive(Debug, Deserialize)]
pub struct State {
    locos: Vec<Loco>,
    devices: Vec<Device>,
    station: Station,
    view: View,
    audio_devices: Vec<String>,
    audio_targets: BTreeMap<String, Vec<String>>,
    audio_latency: BTreeMap<String, i32>,
    audio_conflicts: Vec<u16>,
}

#[derive(Debug, Deserialize)]
struct Loco {
    id: i32,
    name: String,
    max_speed: f32,
    volume: f32,
    speed: f32,
    forward: bool,
    picture: Option<String>,
    sound_model: Option<IgnoredAny>,
    sound: String,
    sound_functions: Vec<Switch>,
    event_sounds: Vec<Switch>,
    functions: Vec<Switch>,
    audio_instance: Option<String>,
    audio_device: Option<String>,
    decoder: Decoder,
}

#[derive(Debug, Deserialize)]
struct Decoder {
    address: u16,
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
    number: i32,
    focus: bool,
}

#[derive(Debug, Deserialize)]
struct View {
    auto_focus: bool,
    only_active: bool,
}

#[derive(Debug, Deserialize)]
struct Station {
    connected: bool,
    track_power: bool,
}

pub fn show(window: &MainWindow, state: &State, media: &Path) {
    window.set_connected(state.station.connected);
    window.set_track_power(state.station.track_power);
    window.set_auto_focus(state.view.auto_focus);
    window.set_only_active(state.view.only_active);
    let rows = controllers(state, media);
    let buttons = rows.iter().map(|c| c.buttons.row_count()).max();
    window.set_button_rows(buttons.unwrap_or(0) as i32);
    let model = window.get_controllers();
    let focused = focus(state, &model);
    let index = focused.and_then(|loco| rows.iter().position(|c| c.id == loco));
    update_controllers(&model, rows);
    let targets = audio_targets(state);
    window.set_audio_targets(ModelRc::new(VecModel::from(targets)));
    if let Some(index) = index {
        window.invoke_bring_into_view(index as i32);
    }
}

/// The loco to bring into view (B-22): the one of a device that holds
/// "focus", else with auto-focus the one a device has changed to, which
/// is not `shown` with that device yet.
pub(crate) fn focus(state: &State, shown: &ModelRc<Controller>) -> Option<i32> {
    let devices = || state.devices.iter().filter(|d| d.loco.is_some());
    let changed = |d: &&Device| {
        !shown
            .iter()
            .any(|c| Some(c.id) == d.loco && c.devices.iter().any(|number| number == d.number))
    };
    if let Some(device) = devices().find(|d| d.focus) {
        return device.loco;
    }
    if !state.view.auto_focus {
        return None;
    }
    devices().find(changed).and_then(|d| d.loco)
}

/// Keeps the models of the buttons and devices, see [`update`].
fn update_controllers(model: &ModelRc<Controller>, mut rows: Vec<Controller>) {
    for (row, old) in rows.iter_mut().zip(model.iter()) {
        update(&old.buttons, row.buttons.iter().collect());
        update(&old.devices, row.devices.iter().collect());
        row.buttons = old.buttons;
        row.devices = old.devices;
    }
    update(model, rows);
}

/// Changes only the rows that changed, so the elements in the window stay;
/// a button held down gets its release even when its state changes.
fn update<T: Clone + PartialEq + 'static>(model: &ModelRc<T>, rows: Vec<T>) {
    let Some(model) = model.as_any().downcast_ref::<VecModel<T>>() else {
        return;
    };
    if model.row_count() != rows.len() {
        model.set_vec(rows);
        return;
    }
    for (index, row) in rows.into_iter().enumerate() {
        if model.row_data(index).as_ref() != Some(&row) {
            model.set_row_data(index, row);
        }
    }
}

/// With the filter "only active" just the locos that are controlled or
/// moving.
pub(crate) fn controllers(state: &State, media: &Path) -> Vec<Controller> {
    let active = |l: &&Loco| l.speed > 0.0 || state.devices.iter().any(|d| d.loco == Some(l.id));
    state
        .locos
        .iter()
        .filter(|l| !state.view.only_active || active(l))
        .map(|l| controller(state, l, media))
        .collect()
}

fn controller(state: &State, loco: &Loco, media: &Path) -> Controller {
    let picture = loco
        .picture
        .as_ref()
        .and_then(|name| Image::load_from_path(&picture::path(media, name)).ok())
        .unwrap_or_default();
    let devices: Vec<i32> = state
        .devices
        .iter()
        .filter(|d| d.loco == Some(loco.id))
        .map(|d| d.number)
        .collect();
    Controller {
        id: loco.id,
        name: loco.name.as_str().into(),
        picture,
        volume: loco.volume,
        speed: loco.speed,
        max_speed: loco.max_speed,
        forward: loco.forward,
        buttons: ModelRc::new(VecModel::from(buttons(loco))),
        devices: ModelRc::new(VecModel::from(devices)),
        audio_target: audio_target(state, loco),
        audio_conflict: state.audio_conflicts.contains(&loco.decoder.address),
    }
}

/// The output devices of the host, then those of the other instances, each
/// with its default device first and the round trip to it (N-05). A target
/// a loco names that is not connected comes last, so the window still
/// shows it.
pub(crate) fn audio_targets(state: &State) -> Vec<AudioTarget> {
    let others = state.audio_targets.iter().map(|(i, d)| (i.as_str(), d));
    let mut targets = Vec::new();
    for (instance, devices) in std::iter::once(("", &state.audio_devices)).chain(others) {
        let latency = latency(state, instance);
        for device in std::iter::once("").chain(devices.iter().map(String::as_str)) {
            let (instance, device) = (instance.into(), device.into());
            targets.push(AudioTarget {
                instance,
                device,
                latency,
            });
        }
    }
    for target in state.locos.iter().map(|l| audio_target(state, l)) {
        if !targets.contains(&target) {
            targets.push(target);
        }
    }
    targets
}

/// Empty is the host or its default device, like `null` in the state.
fn audio_target(state: &State, loco: &Loco) -> AudioTarget {
    let text = |s: &Option<String>| s.as_deref().unwrap_or_default().into();
    AudioTarget {
        instance: text(&loco.audio_instance),
        device: text(&loco.audio_device),
        latency: latency(state, loco.audio_instance.as_deref().unwrap_or_default()),
    }
}

/// The round trip to the instance, -1 if not measured.
fn latency(state: &State, instance: &str) -> i32 {
    state.audio_latency.get(instance).copied().unwrap_or(-1)
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
