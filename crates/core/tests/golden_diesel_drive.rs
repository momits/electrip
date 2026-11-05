//! B-11, B-12: a drive with the sound of a combustion engine plays the same
//! sounds at the same times as Electrip 1 (`tests/golden/diesel_drive.jsonl`,
//! recorded from the scenario). The host runs with an audio target that
//! plays like the mixer of Electrip 1 on a clock of the test.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

use electrip_core::audio::AudioSink;
use electrip_core::host::Host;
use electrip_core::session::Command;
use electrip_core::station::StationError;
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::sync::{Arc, Mutex};

/// Seconds between two polls of the host, as in the app.
const POLL: f64 = 0.05;

/// The golden file rounds times to microseconds.
const TOLERANCE: f64 = 1e-6;

/// Time, sound and event ("start" or "end") as in the golden file.
type Event = (f64, String, String);

/// A channel that plays a sound and holds one waiting sound, like pygame.
#[derive(Default)]
struct Mixer {
    now: f64,
    lengths: HashMap<String, f64>,
    playing: Option<(String, f64)>,
    waiting: Option<String>,
    events: Vec<Event>,
}

impl Mixer {
    /// Ends sounds up to `now`; a waiting sound follows without a gap.
    fn advance(&mut self, now: f64) {
        while let Some((sound, end)) = self.playing.take_if(|(_, end)| *end <= now) {
            self.events.push((end, sound, "end".into()));
            if let Some(next) = self.waiting.take() {
                self.start(next, end);
            }
        }
        self.now = now;
    }

    fn start(&mut self, sound: String, at: f64) {
        let end = at + self.lengths[&sound];
        self.events.push((at, sound.clone(), "start".into()));
        self.playing = Some((sound, end));
    }
}

struct Sink(Arc<Mutex<Mixer>>);

impl AudioSink for Sink {
    fn length(&mut self, sound: &Path) -> Result<f64, String> {
        let mixer = self.0.lock().unwrap();
        let length = mixer.lengths.get(sound.to_str().unwrap());
        length.copied().ok_or("not in sound_lengths".into())
    }

    fn queue(&mut self, _: u32, sound: &Path) {
        let mut mixer = self.0.lock().unwrap();
        let now = mixer.now;
        mixer.advance(now);
        let sound = sound.to_str().unwrap().to_string();
        if mixer.playing.is_some() {
            mixer.waiting = Some(sound);
        } else {
            mixer.start(sound, now);
        }
    }

    fn stop(&mut self, _: u32) {
        let mut mixer = self.0.lock().unwrap();
        let now = mixer.now;
        mixer.advance(now);
        if let Some((sound, _)) = mixer.playing.take() {
            mixer.events.push((now, sound, "stop".into()));
        }
        mixer.waiting = None;
    }
}

fn read(path: &str) -> String {
    fs::read_to_string(format!("{}/../../{path}", env!("CARGO_MANIFEST_DIR"))).unwrap()
}

/// The command for an input of the scenario on the device of type
/// "Electrip 1".
fn input(entry: &Value, axis: u64) -> Command {
    let (control, value) = if let Some(button) = entry["press"].as_u64() {
        (format!("button{button}"), 1.0)
    } else if let Some(button) = entry["release"].as_u64() {
        (format!("button{button}"), 0.0)
    } else {
        (format!("axis{axis}"), entry["axis"].as_f64().unwrap())
    };
    Command::Input {
        device: 1,
        control,
        value,
    }
}

/// Plays the scenario through a host and returns the sound events.
fn play(scenario: &Value) -> Vec<Event> {
    let dir = tempfile::tempdir().unwrap();
    let config = dir.path().join("diesel_drive.json");
    fs::write(&config, scenario["config"].to_string()).unwrap();
    let lengths = scenario["sound_lengths"].as_object().unwrap();
    let mixer = Arc::new(Mutex::new(Mixer {
        lengths: lengths
            .iter()
            .map(|(k, v)| (k.clone(), v.as_f64().unwrap()))
            .collect(),
        ..Mixer::default()
    }));
    let connect = Box::new(|_: &_| Err(StationError("no station".into())));
    let sink = Box::new(Sink(Arc::clone(&mixer)));
    let mut host = Host::new(connect, sink, dir.path().join("library")).unwrap();
    host.apply(Command::ImportElectrip1 { path: config })
        .unwrap();
    let kind = "Electrip 1".into();
    host.apply(Command::AddDevice { device: 1, kind }).unwrap();

    let axis = scenario["config"]["joystick"]["accel_axis"]
        .as_u64()
        .unwrap();
    let inputs = scenario["input"].as_array().unwrap();
    let until = scenario["until"].as_f64().unwrap();
    let polls = (until / POLL).round() as u32;
    for poll in 0..polls {
        let now = f64::from(poll) * POLL;
        mixer.lock().unwrap().now = now;
        for entry in inputs {
            if (entry["t"].as_f64().unwrap() - now).abs() < 1e-6 {
                host.apply(input(entry, axis)).unwrap();
            }
        }
        mixer.lock().unwrap().now = now + POLL;
        host.poll(POLL);
    }
    let mut mixer = mixer.lock().unwrap();
    mixer.advance(until);
    std::mem::take(&mut mixer.events)
}

#[test]
fn diesel_drive_matches_electrip_1() {
    let scenario: Value =
        serde_json::from_str(&read("tests/golden/scenarios/diesel_drive.json")).unwrap();
    let golden: Vec<Event> = read("tests/golden/diesel_drive.jsonl")
        .lines()
        .map(|line| serde_json::from_str::<Value>(line).unwrap())
        .filter(|entry| entry["sound"].is_string())
        .map(|e| {
            let text = |key: &str| e[key].as_str().unwrap().to_string();
            (e["t"].as_f64().unwrap(), text("sound"), text("ev"))
        })
        .collect();
    let played = play(&scenario);
    for (nr, (old, new)) in golden.iter().zip(&played).enumerate() {
        let same = old.1 == new.1 && old.2 == new.2 && (old.0 - new.0).abs() <= TOLERANCE;
        assert!(
            same,
            "sound event {nr}: Electrip 1 {old:?}, Electrip 2 {new:?}"
        );
    }
    assert_eq!(golden.len(), played.len(), "{played:?}");
}
