use super::*;
use crate::audio::tests::LogSink;
use crate::sound::{Engine, Steam};
use std::path::PathBuf;

/// A steam engine with segments from 0 and 50 km/h, strokes "a1" to "a4"
/// and "b1" to "b4" and a start delay of 0.5 s. Large wheels and at least
/// ten strokes per second make the pause 0.1 s up to 80 km/h.
fn model() -> SoundModel {
    let mut model = SoundModel::new(Engine::Steam);
    model.insert_segment(0, 100.0).unwrap();
    model.set_sound(EngineSound::Idle, Some(PathBuf::from("idle")));
    model.set_sound(EngineSound::Cylinder, Some(PathBuf::from("steam")));
    let steam = Steam {
        wheel_diameter: 3.0,
        start_delay: 0.5,
        min_frequency: 10.0,
        ..Steam::default()
    };
    model.set_steam(steam).unwrap();
    for (nr, segment) in ["a", "b"].iter().enumerate() {
        for stroke in 0..4 {
            let path = PathBuf::from(format!("{segment}{}", stroke + 1));
            model.set_stroke_sound(nr, stroke, Some(path)).unwrap();
        }
    }
    model
}

/// Idle and steam last one second.
fn sink() -> LogSink {
    LogSink::new(&[("idle", 1.0), ("steam", 1.0)])
}

fn ms(ms: u64) -> Duration {
    Duration::from_millis(ms)
}

/// A running engine at standstill.
fn started(sink: &mut LogSink) -> SteamSound {
    let mut sound = SteamSound::new(1);
    sound.start(&model(), 0.0, sink);
    sink.take();
    sound
}

#[test]
fn the_idle_sound_loops_while_the_engine_runs() {
    let mut sink = sink();
    let mut sound = SteamSound::new(1);
    sound.start(&model(), 0.0, &mut sink);
    assert!(sound.is_running());
    assert_eq!(sink.take(), ["1 idle", "1 idle"]);
    sound.play(&model(), 0.0, &mut sink, ms(1000));
    assert_eq!(sink.take(), ["1 idle"]);
}

#[test]
fn moving_off_blows_off_steam_and_strokes_after_the_delay() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    sound.play(&model(), 1.0, &mut sink, ms(250));
    assert_eq!(sink.take(), ["1.1 steam"]);
    sound.play(&model(), 1.0, &mut sink, ms(250));
    assert_eq!(sink.take(), ["1.2 a1 after 250ms"]);
    sound.play(&model(), 1.0, &mut sink, ms(250));
    assert_eq!(sink.take(), ["1.3 a2 after 100ms", "1.4 a3 after 200ms"]);
}

#[test]
fn the_strokes_go_on_at_once_while_the_steam_blows() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    sound.play(&model(), 1.0, &mut sink, ms(250));
    sound.play(&model(), 1.0, &mut sink, ms(250));
    sound.play(&model(), 0.0, &mut sink, ms(250));
    sink.take();
    sound.play(&model(), 1.0, &mut sink, ms(50));
    assert_eq!(sink.take(), ["1.3 a2 after 0ns"]);
    sound.play(&model(), 0.0, &mut sink, ms(50));
    sound.play(&model(), 1.0, &mut sink, ms(400));
    assert_eq!(sink.take(), ["1 idle", "1.1 steam"]);
}

#[test]
fn the_strokes_come_from_the_segment_of_the_speed() {
    let mut sink = sink();
    let mut sound = SteamSound::new(1);
    sound.start(&model(), 60.0, &mut sink);
    sink.take();
    sound.play(&model(), 60.0, &mut sink, ms(100));
    assert_eq!(sink.take(), ["1.2 b1 after 0ns", "1.3 b2 after 100ms"]);
    sound.play(&model(), 1.0, &mut sink, ms(100));
    assert_eq!(sink.take(), ["1.4 a3 after 100ms"]);
}

#[test]
fn stopping_silences_every_channel() {
    let mut sink = sink();
    let mut sound = started(&mut sink);
    sound.stop(&mut sink);
    assert!(!sound.is_running());
    let channels = ["1", "1.1", "1.2", "1.3", "1.4", "1.5"];
    assert_eq!(sink.take(), channels.map(|c| format!("{c} stop")));
}
