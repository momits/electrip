use super::*;
use crate::audio::tests::LogSink;
use std::path::PathBuf;

/// A combustion engine with segments from 0 and 50 km/h; every sound lasts
/// one second.
fn model() -> SoundModel {
    let mut model = SoundModel::new(Engine::Diesel);
    model.insert_segment(0, 100.0).unwrap();
    for (sound, name) in [
        (EngineSound::Start, "start"),
        (EngineSound::Idle, "idle"),
        (EngineSound::Quit, "quit"),
    ] {
        model.set_sound(sound, Some(PathBuf::from(name)));
    }
    for nr in 0..2 {
        for (sound, name) in [
            (SegmentSound::Load, "load"),
            (SegmentSound::Idle, "idle"),
            (SegmentSound::Accel, "accel"),
            (SegmentSound::Decel, "decel"),
        ] {
            let path = PathBuf::from(format!("{name}{}", nr + 1));
            model.set_segment_sound(nr, sound, Some(path)).unwrap();
        }
    }
    model
}

fn sink() -> LogSink {
    let names = ["start", "idle", "quit", "load", "accel", "decel"];
    let mut lengths: Vec<(String, f64)> = names.iter().map(|n| (n.to_string(), 1.0)).collect();
    for nr in 1..=2 {
        lengths.extend(names[1..].iter().map(|n| (format!("{n}{nr}"), 1.0)));
    }
    LogSink {
        lengths: lengths.into_iter().collect(),
        ..LogSink::default()
    }
}

/// Lets one sound after the other end at `speed`.
fn play(sound: &mut DrivingSound, sink: &mut LogSink, speed: f64, sounds: usize) {
    for _ in 0..sounds {
        sound.play(Some(&model()), speed, sink, Duration::from_secs(1));
    }
}

/// A sound that started at standstill and reached the idle sound.
fn started(sink: &mut LogSink) -> DrivingSound {
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&model()), 0.0, sink);
    play(&mut sound, sink, 0.0, 1);
    sink.take();
    sound
}

#[test]
fn starting_plays_the_start_sound_and_locks_the_speed_until_idle() {
    let mut sink = sink();
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&model()), 0.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Starting);
    assert!(sound.locks_speed());
    assert_eq!(sink.take(), ["1 start", "1 idle"]);
    sound.toggle(Some(&model()), 0.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Starting);

    play(&mut sound, &mut sink, 0.0, 1);
    assert_eq!(sound.state(), SoundState::On);
    assert!(!sound.locks_speed());
    assert_eq!(sink.take(), ["1 idle"]);
}

#[test]
fn accelerating_climbs_one_segment_per_sound_and_loops_the_load_sound() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    play(&mut sound, &mut sink, 80.0, 4);
    assert_eq!(sink.take(), ["1 accel1", "1 accel2", "1 load2", "1 load2"]);
}

#[test]
fn braking_falls_one_segment_per_sound_and_loops_the_idle_sound() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    play(&mut sound, &mut sink, 80.0, 2);
    play(&mut sound, &mut sink, 30.0, 2);
    play(&mut sound, &mut sink, 0.0, 2);
    let played = sink.take();
    assert_eq!(played[2..], ["1 decel2", "1 idle1", "1 decel1", "1 idle"]);
}

#[test]
fn stopping_waits_for_the_idle_sound_then_quits() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    sound.toggle(Some(&model()), 0.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Stopping);
    assert!(sound.locks_speed());
    play(&mut sound, &mut sink, 0.0, 1);
    assert_eq!(sink.take(), ["1 idle", "1 quit"]);
    play(&mut sound, &mut sink, 0.0, 1);
    assert_eq!(sound.state(), SoundState::Stopping);
    play(&mut sound, &mut sink, 0.0, 1);
    assert_eq!(sound.state(), SoundState::Off);
    assert!(sink.take().is_empty());
}

#[test]
fn switching_while_driving_starts_with_the_load_sound_and_stops_at_once() {
    let mut sink = sink();
    let mut sound = DrivingSound::new(2);
    sound.toggle(Some(&model()), 60.0, &mut sink);
    assert_eq!(sound.state(), SoundState::On);
    sound.toggle(Some(&model()), 60.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Off);
    assert_eq!(sink.take(), ["2 load2", "2 load2", "2 stop"]);
}

#[test]
fn without_sounds_or_with_steam_the_sound_stays_off() {
    let mut sink = LogSink::default();
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&model()), 0.0, &mut sink);
    sound.toggle(Some(&SoundModel::new(Engine::Steam)), 0.0, &mut sink);
    sound.toggle(None, 0.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Off);
}

#[test]
fn removing_the_model_stops_the_sound() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    sound.play(None, 0.0, &mut sink, Duration::ZERO);
    assert_eq!(sound.state(), SoundState::Off);
    assert_eq!(sink.take(), ["1 stop"]);
}

#[test]
fn the_state_shows_only_whether_the_sound_is_on() {
    let value = serde_json::to_value(DrivingSound::new(1)).unwrap();
    assert_eq!(value, "off");
}
