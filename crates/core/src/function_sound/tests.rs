use super::*;
use crate::audio::tests::LogSink;

/// A function of action 1 playing "horn", which lasts one second.
fn horn(mode: SoundMode) -> SoundFunction {
    SoundFunction {
        action: 1,
        mode,
        path: Some("horn".into()),
        ..SoundFunction::default()
    }
}

fn sink() -> LogSink {
    LogSink::new(&[("horn", 1.0), ("bell", 3.0)])
}

fn trigger_horn(functions: &mut [SoundFunction], pressed: bool, sink: &mut LogSink) {
    trigger(functions, 7, 1, pressed, sink);
}

fn play(functions: &mut [SoundFunction], seconds: f64, sink: &mut LogSink) {
    for function in functions {
        function.play(sink, Duration::from_secs_f64(seconds));
    }
}

#[test]
fn a_switch_loops_until_the_second_press() {
    let (mut sink, mut functions) = (sink(), [horn(SoundMode::Switch)]);
    trigger_horn(&mut functions, true, &mut sink);
    trigger_horn(&mut functions, false, &mut sink);
    assert_eq!(sink.take(), ["7.10001 horn", "7.10001 horn"]);
    play(&mut functions, 1.5, &mut sink);
    assert_eq!(sink.take(), ["7.10001 horn"]);
    assert!(functions[0].on);

    trigger_horn(&mut functions, true, &mut sink);
    trigger_horn(&mut functions, false, &mut sink);
    assert_eq!(sink.take(), ["7.10001 stop"]);
    assert!(!functions[0].on);
}

#[test]
fn a_push_button_loops_while_held() {
    let (mut sink, mut functions) = (sink(), [horn(SoundMode::Push)]);
    trigger_horn(&mut functions, true, &mut sink);
    play(&mut functions, 2.5, &mut sink);
    assert_eq!(sink.take(), ["7.10001 horn"; 4]);
    trigger_horn(&mut functions, false, &mut sink);
    assert_eq!(sink.take(), ["7.10001 stop"]);
    assert!(!functions[0].on);
}

#[test]
fn a_push_once_button_plays_once_and_stops_on_release() {
    let (mut sink, mut functions) = (sink(), [horn(SoundMode::PushOnce)]);
    trigger_horn(&mut functions, true, &mut sink);
    play(&mut functions, 2.5, &mut sink);
    assert_eq!(sink.take(), ["7.10001 horn"]);
    trigger_horn(&mut functions, false, &mut sink);
    assert_eq!(sink.take(), ["7.10001 stop"]);

    trigger_horn(&mut functions, true, &mut sink);
    play(&mut functions, 0.5, &mut sink);
    trigger_horn(&mut functions, false, &mut sink);
    assert_eq!(sink.take(), ["7.10001 horn", "7.10001 stop"]);
}

#[test]
fn a_tap_plays_to_the_end_whatever_happens() {
    let (mut sink, mut functions) = (sink(), [horn(SoundMode::Tap)]);
    trigger_horn(&mut functions, true, &mut sink);
    trigger_horn(&mut functions, false, &mut sink);
    play(&mut functions, 0.5, &mut sink);
    trigger_horn(&mut functions, true, &mut sink);
    trigger_horn(&mut functions, false, &mut sink);
    assert_eq!(sink.take(), ["7.10001 horn"]);
    assert!(functions[0].on);

    let mut function = functions[0].clone();
    assert!(function.play(&mut sink, Duration::from_secs_f64(0.5)));
    assert!(!function.on);
    assert!(sink.take().is_empty());
}

#[test]
fn a_tap_without_a_sound_switches_off_at_the_next_poll() {
    let mut sink = sink();
    let mut functions = [SoundFunction {
        path: None,
        ..horn(SoundMode::Tap)
    }];
    trigger_horn(&mut functions, true, &mut sink);
    assert!(functions[0].on);
    play(&mut functions, 0.05, &mut sink);
    assert!(!functions[0].on);
    assert!(sink.take().is_empty());
}

#[test]
fn each_playing_function_has_its_own_channel() {
    let bell = SoundFunction {
        path: Some("bell".into()),
        ..horn(SoundMode::Tap)
    };
    let other = SoundFunction {
        action: 2,
        ..horn(SoundMode::Tap)
    };
    let mut sink = sink();
    let mut functions = [bell, horn(SoundMode::Tap), other];
    trigger_horn(&mut functions, true, &mut sink);
    play(&mut functions, 1.5, &mut sink);
    trigger(&mut functions, 7, 2, true, &mut sink);
    assert_eq!(
        sink.take(),
        ["7.10001 bell", "7.10002 horn", "7.10002 horn"]
    );
}
