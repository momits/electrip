//! Plays a drive of `tests/golden/scenarios` through a host with an audio
//! target that plays like the mixer of Electrip 1 on a clock of the test,
//! for the golden tests of the driving sound.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

use electrip_core::audio::{AudioSink, ChannelId};
use electrip_core::decoder::Decoder;
use electrip_core::host::Host;
use electrip_core::session::Command;
use electrip_core::station::{CommandStation, LocoState, StationError, StationEvent};
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::Duration;

/// Seconds between two polls of the host, as in the app.
pub const POLL: f64 = 0.05;

/// Time, sound and event ("start", "end", "stop" or "replaced") as in the
/// golden file, or time, "GL" and loco state.
pub type Event = (f64, String, String);

/// A channel that plays a sound and holds one waiting sound, like pygame,
/// and a sound to play later.
#[derive(Default)]
struct Track {
    playing: Option<(String, f64)>,
    waiting: Option<String>,
    delayed: Option<(String, f64)>,
}

#[derive(Default)]
struct Mixer {
    now: f64,
    lengths: HashMap<String, f64>,
    tracks: HashMap<ChannelId, Track>,
    events: Vec<Event>,
}

impl Mixer {
    /// Ends and starts sounds up to `now`; a waiting sound follows without
    /// a gap, a delayed one cuts off the playing one.
    fn advance(&mut self, now: f64) {
        for track in self.tracks.values_mut() {
            loop {
                let end = track.playing.as_ref().map_or(f64::INFINITY, |p| p.1);
                let at = track.delayed.as_ref().map_or(f64::INFINITY, |d| d.1);
                if end.min(at) > now {
                    break;
                }
                let (next, start, event) = if end <= at {
                    (track.waiting.take(), end, "end")
                } else {
                    (track.delayed.take().map(|d| d.0), at, "replaced")
                };
                if let Some((sound, _)) = track.playing.take() {
                    self.events.push((start, sound, event.into()));
                }
                if let Some(sound) = next {
                    let end = start + self.lengths[&sound];
                    self.events.push((start, sound.clone(), "start".into()));
                    track.playing = Some((sound, end));
                }
            }
        }
        self.now = now;
    }

    /// The track of the channel after advancing to now.
    fn track(&mut self, channel: ChannelId) -> &mut Track {
        self.advance(self.now);
        self.tracks.entry(channel).or_default()
    }
}

struct Sink(Arc<Mutex<Mixer>>);

impl AudioSink for Sink {
    fn length(&mut self, sound: &Path) -> Result<Duration, String> {
        let mixer = self.0.lock().unwrap();
        let length = mixer.lengths.get(sound.to_str().unwrap());
        let length = length.ok_or("not in sound_lengths")?;
        Ok(Duration::from_secs_f64(*length))
    }

    fn queue(&mut self, channel: ChannelId, sound: &Path) {
        let sound = sound.to_str().unwrap().to_string();
        let mut mixer = self.0.lock().unwrap();
        let now = mixer.now;
        let track = mixer.track(channel);
        if track.playing.is_some() {
            track.waiting = Some(sound);
        } else {
            track.delayed = Some((sound, now));
            mixer.advance(now);
        }
    }

    fn play(&mut self, channel: ChannelId, sound: &Path, delay: Duration) {
        let sound = sound.to_str().unwrap().to_string();
        let mut mixer = self.0.lock().unwrap();
        let at = mixer.now + delay.as_secs_f64();
        mixer.track(channel).delayed = Some((sound, at));
        let now = mixer.now;
        mixer.advance(now);
    }

    fn stop(&mut self, channel: ChannelId) {
        let mut mixer = self.0.lock().unwrap();
        let now = mixer.now;
        let track = mixer.track(channel);
        let stopped = track.playing.take();
        track.waiting = None;
        track.delayed = None;
        if let Some((sound, _)) = stopped {
            mixer.events.push((now, sound, "stop".into()));
        }
    }
}

/// A command station that logs the loco states it gets like the SRCP
/// command `SET 1 GL` of Electrip 1: direction, step and F0.
struct Station(Arc<Mutex<Mixer>>, Arc<Mutex<Vec<Event>>>);

impl CommandStation for Station {
    fn set_power(&mut self, _: bool) -> Result<(), StationError> {
        Ok(())
    }

    fn set_loco(&mut self, _: &Decoder, state: &LocoState) -> Result<(), StationError> {
        let now = self.0.lock().unwrap().now;
        let state = format!(
            "{} {} 128 {}",
            u8::from(state.forward),
            state.step,
            u8::from(state.function(0))
        );
        self.1.lock().unwrap().push((now, "GL".into(), state));
        Ok(())
    }

    fn emergency_stop(&mut self, decoder: &Decoder, state: &LocoState) -> Result<(), StationError> {
        self.set_loco(decoder, state)
    }

    fn events(&mut self) -> Vec<StationEvent> {
        Vec::new()
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

/// Plays the scenario `name` through a host and returns the sound events
/// in the order of time and the loco states the command station got.
pub fn play(name: &str) -> (Vec<Event>, Vec<Event>) {
    let scenario: Value =
        serde_json::from_str(&read(&format!("tests/golden/scenarios/{name}.json"))).unwrap();
    let dir = tempfile::tempdir().unwrap();
    let config = dir.path().join(format!("{name}.json"));
    fs::write(&config, scenario["config"].to_string()).unwrap();
    let lengths = scenario["sound_lengths"].as_object().unwrap();
    let mixer = Arc::new(Mutex::new(Mixer {
        lengths: lengths
            .iter()
            .map(|(k, v)| (k.clone(), v.as_f64().unwrap()))
            .collect(),
        ..Mixer::default()
    }));
    let sent = Arc::new(Mutex::new(Vec::new()));
    let station = Station(Arc::clone(&mixer), Arc::clone(&sent));
    let mut station = Some(station);
    let connect = Box::new(move |_: &_| {
        let station = station
            .take()
            .ok_or(StationError("connected twice".into()))?;
        Ok(Box::new(station) as _)
    });
    let sink = Box::new(Sink(Arc::clone(&mixer)));
    let mut host = Host::new(connect, sink, dir.path().join("library")).unwrap();
    host.apply(Command::ImportElectrip1 { path: config })
        .unwrap();
    host.apply(Command::Connect).unwrap();
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
    let mut events = std::mem::take(&mut mixer.events);
    events.sort_by(|a, b| a.0.total_cmp(&b.0));
    let sent = std::mem::take(&mut *sent.lock().unwrap());
    (events, sent)
}

/// The entries of the golden file `name`: sounds as (time, sound, event),
/// states of the loco at `address` as (time, "GL", state).
pub fn golden(name: &str, address: u16) -> (Vec<Event>, Vec<Event>) {
    let entries: Vec<Value> = read(&format!("tests/golden/{name}.jsonl"))
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    let sounds = entries
        .iter()
        .filter(|entry| entry["sound"].is_string())
        .map(|e| {
            let text = |key: &str| e[key].as_str().unwrap().to_string();
            (e["t"].as_f64().unwrap(), text("sound"), text("ev"))
        })
        .collect();
    let prefix = format!("SET 1 GL {address} ");
    let states = entries
        .iter()
        .filter_map(|e| {
            let state = e["srcp"].as_str()?.strip_prefix(&prefix)?;
            Some((e["t"].as_f64().unwrap(), "GL".into(), state.into()))
        })
        .collect();
    (sounds, states)
}

/// Asserts that both lists hold the same events at the same times, within
/// `tolerance` seconds.
pub fn assert_same(what: &str, golden: &[Event], played: &[Event], tolerance: f64) {
    for (nr, (old, new)) in golden.iter().zip(played).enumerate() {
        let same = old.1 == new.1 && old.2 == new.2 && (old.0 - new.0).abs() <= tolerance;
        assert!(same, "{what} {nr}: Electrip 1 {old:?}, Electrip 2 {new:?}");
    }
    assert_eq!(golden.len(), played.len(), "{what}: {played:?}");
}
