use super::*;
use crate::audio::tests::LogSink;
use crate::decoder::{Decoder, Protocol};
use crate::loco::Loco;

/// The squeal of action 1, lasting 2 s: up to 30 km/h while braking
/// harder than 2 km/h per second.
fn squeal() -> EventSound {
    EventSound {
        action: 1,
        path: Some("squeal".into()),
        max_speed: Some(30.0),
        max_accel: Some(-2.0),
        fade_out: 0.5,
        default_active: true,
        active: true,
        ..EventSound::default()
    }
}

fn sink() -> LogSink {
    LogSink::new(&[("squeal", 2.0)])
}

/// A loco at `speed` km/h, forward unless reversed.
fn motion(speed: f64, forward: bool) -> Motion {
    let loco = Loco::new(Decoder::new(Protocol::DccShort, 3, 128).unwrap(), 100.0).unwrap();
    let mut motion = Motion::default();
    if !forward {
        motion.reverse();
    }
    motion.accelerate(&loco, 1.0, speed / 100.0 * loco.accel_duration());
    motion
}

/// Plays the sounds of loco 7 for `seconds` at `speed` and `accel`.
fn tick(sounds: &mut [EventSound], speed: f64, accel: f64, seconds: f64, sink: &mut LogSink) {
    let moving = Some((motion(speed, true), accel));
    play(sounds, 7, moving, sink, Duration::from_secs_f64(seconds));
}

fn channel(index: usize) -> String {
    format!("7.{}", channel_nr(index))
}

#[test]
fn bounds_and_direction_decide_whether_it_holds() {
    let sound = squeal();
    assert!(sound.holds(&motion(30.0, true), -2.0));
    assert!(sound.holds(&motion(0.0, false), -20.0));
    assert!(!sound.holds(&motion(31.0, true), -20.0));
    assert!(!sound.holds(&motion(20.0, true), -1.0));
    let forward = EventSound {
        forward: Some(true),
        min_speed: Some(0.0),
        ..sound.clone()
    };
    assert!(forward.holds(&motion(20.0, true), -5.0));
    assert!(!forward.holds(&motion(20.0, false), -5.0));
    let inactive = EventSound {
        active: false,
        ..sound
    };
    assert!(!inactive.holds(&motion(20.0, true), -5.0));
}

#[test]
fn it_loops_while_it_holds_and_fades_out_once_after() {
    let (mut sink, mut sounds) = (sink(), [squeal()]);
    tick(&mut sounds, 20.0, -10.0, 0.05, &mut sink);
    tick(&mut sounds, 19.5, -10.0, 1.0, &mut sink);
    assert_eq!(sink.take(), [format!("{} squeal fade in 0ns", channel(0))]);
    tick(&mut sounds, 10.0, -10.0, 1.0, &mut sink);
    assert_eq!(sink.take(), [format!("{} squeal fade in 0ns", channel(0))]);
    tick(&mut sounds, 0.0, 0.0, 0.05, &mut sink);
    tick(&mut sounds, 0.0, 0.0, 0.05, &mut sink);
    assert_eq!(sink.take(), [format!("{} fade out 500ms", channel(0))]);
    // The fade ends the sound; braking again starts it anew.
    tick(&mut sounds, 0.0, 0.0, 0.5, &mut sink);
    tick(&mut sounds, 20.0, -10.0, 0.05, &mut sink);
    assert_eq!(sink.take(), [format!("{} squeal fade in 0ns", channel(0))]);
}

#[test]
fn played_to_the_end_it_does_not_fade_out() {
    let sound = EventSound {
        play_to_end: true,
        fade_in: 0.3,
        ..squeal()
    };
    let (mut sink, mut sounds) = (sink(), [sound]);
    tick(&mut sounds, 20.0, -10.0, 0.05, &mut sink);
    tick(&mut sounds, 30.0, 10.0, 1.9, &mut sink);
    tick(&mut sounds, 30.0, 10.0, 1.0, &mut sink);
    assert_eq!(
        sink.take(),
        [format!("{} squeal fade in 300ms", channel(0))]
    );
}

#[test]
fn without_a_driving_sound_none_plays() {
    let (mut sink, mut sounds) = (sink(), [squeal()]);
    play(&mut sounds, 7, None, &mut sink, Duration::from_millis(50));
    assert_eq!(sink.take(), Vec::<String>::new());
}

#[test]
fn each_event_sound_has_its_own_channel() {
    let (mut sink, mut sounds) = (sink(), [squeal(), squeal()]);
    tick(&mut sounds, 20.0, -10.0, 0.05, &mut sink);
    assert_eq!(
        sink.take(),
        [
            format!("{} squeal fade in 0ns", channel(0)),
            format!("{} squeal fade in 0ns", channel(1)),
        ]
    );
}
