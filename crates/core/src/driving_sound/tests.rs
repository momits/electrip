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
        sound.play(Some(&model()), speed, 100.0, sink, Duration::from_secs(1));
    }
}

/// A sound that started at standstill and reached the idle sound.
fn started(sink: &mut LogSink) -> DrivingSound {
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&model()), 0.0, 100.0, sink);
    play(&mut sound, sink, 0.0, 1);
    sink.take();
    sound
}

#[test]
fn starting_plays_the_start_sound_and_locks_the_speed_until_idle() {
    let mut sink = sink();
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&model()), 0.0, 100.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Starting);
    assert!(sound.locks_speed());
    assert_eq!(sink.take(), ["1 start", "1 idle"]);
    sound.toggle(Some(&model()), 0.0, 100.0, &mut sink);
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
    sound.toggle(Some(&model()), 0.0, 100.0, &mut sink);
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
    sound.toggle(Some(&model()), 60.0, 100.0, &mut sink);
    assert_eq!(sound.state(), SoundState::On);
    sound.toggle(Some(&model()), 60.0, 100.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Off);
    assert_eq!(sink.take(), ["2 load2", "2 load2", "2 stop"]);
}

#[test]
fn without_sounds_or_a_model_the_sound_stays_off() {
    let mut sink = LogSink::default();
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&model()), 0.0, 100.0, &mut sink);
    sound.toggle(None, 0.0, 100.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Off);
}

#[test]
fn a_steam_engine_switches_on_and_off_at_once() {
    let steam = SoundModel::new(Engine::Steam);
    let mut sink = LogSink::default();
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&steam), 0.0, 100.0, &mut sink);
    assert_eq!(sound.state(), SoundState::On);
    assert!(!sound.locks_speed());
    sound.toggle(Some(&steam), 0.0, 100.0, &mut sink);
    assert_eq!(sound.state(), SoundState::Off);
}

#[test]
fn a_steam_engine_does_not_hold_back_the_loco() {
    let mut sound = DrivingSound::new(1);
    sound.toggle(
        Some(&SoundModel::new(Engine::Steam)),
        0.0,
        100.0,
        &mut sink(),
    );
    let state = LocoState {
        step: 5,
        ..LocoState::default()
    };
    assert_eq!(sound.synchronize(state, &LocoState::default()), state);
}

#[test]
fn a_model_of_another_engine_stops_the_sound() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    let steam = SoundModel::new(Engine::Steam);
    sound.play(Some(&steam), 0.0, 100.0, &mut sink, Duration::ZERO);
    assert_eq!(sound.state(), SoundState::Off);
    assert_eq!(sink.take(), ["1 stop"]);
}

#[test]
fn removing_the_model_stops_the_sound() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    sound.play(None, 0.0, 100.0, &mut sink, Duration::ZERO);
    assert_eq!(sound.state(), SoundState::Off);
    assert_eq!(sink.take(), ["1 stop"]);
}

#[test]
fn the_state_shows_whether_the_sound_is_on_and_its_level() {
    let value = serde_json::to_value(DrivingSound::new(1)).unwrap();
    assert_eq!(
        value,
        serde_json::json!({"sound": "off", "sound_level": 0.0})
    );
}

#[test]
fn the_level_moves_evenly_to_the_end_of_the_segment_the_sound_leads_to() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    let mut level_after = |ms| {
        let elapsed = Duration::from_millis(ms);
        sound.play(Some(&model()), 60.0, 100.0, &mut sink, elapsed);
        sound.sound_level()
    };
    assert_eq!(level_after(1000), 0.0);
    assert_eq!(level_after(1000), 0.0);
    assert_eq!(level_after(500), 25.0);
    assert_eq!(level_after(500), 50.0);
    assert_eq!(level_after(250), 62.5);
    assert_eq!(level_after(750), 100.0);
}

#[test]
fn switching_while_driving_sets_the_level_and_switching_off_clears_it() {
    let mut sink = sink();
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&model()), 40.0, 100.0, &mut sink);
    assert_eq!(sound.sound_level(), 50.0);
    sound.toggle(Some(&model()), 40.0, 100.0, &mut sink);
    assert_eq!(sound.sound_level(), 0.0);
}

#[test]
fn the_level_of_a_steam_engine_is_the_speed() {
    let steam = SoundModel::new(Engine::Steam);
    let mut sink = LogSink::default();
    let mut sound = DrivingSound::new(1);
    sound.toggle(Some(&steam), 30.0, 100.0, &mut sink);
    assert_eq!(sound.sound_level(), 30.0);
    sound.play(Some(&steam), 40.0, 100.0, &mut sink, Duration::ZERO);
    assert_eq!(sound.sound_level(), 40.0);
    sound.toggle(Some(&steam), 40.0, 100.0, &mut sink);
    assert_eq!(sound.sound_level(), 0.0);
}

#[test]
fn the_loco_starts_and_stops_with_the_sound_of_the_first_segment() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    let last = LocoState {
        forward: true,
        step: 0,
        functions: 1,
    };
    let driving = LocoState { step: 5, ..last };
    play(&mut sound, &mut sink, 10.0, 1);
    assert_eq!(sink.take(), ["1 accel1"]);
    assert_eq!(sound.synchronize(driving, &last), last);
    play(&mut sound, &mut sink, 10.0, 1);
    assert_eq!(sound.synchronize(driving, &last), driving);

    let stopping = LocoState {
        forward: false,
        ..last
    };
    play(&mut sound, &mut sink, 0.0, 1);
    assert_eq!(sink.take(), ["1 load1", "1 decel1"]);
    assert_eq!(sound.synchronize(stopping, &driving), driving);
    play(&mut sound, &mut sink, 0.0, 1);
    assert_eq!(sound.synchronize(stopping, &driving), stopping);
}

#[test]
fn without_sound_the_loco_is_not_held() {
    let state = LocoState {
        step: 5,
        ..LocoState::default()
    };
    let sound = DrivingSound::new(1);
    assert_eq!(sound.synchronize(state, &LocoState::default()), state);
}
