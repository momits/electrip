use super::*;
use crate::decoder::Protocol::*;
use crate::sound::{Engine, SoundModel};

/// A DCC loco at 100 km/h whose curve has an extra point, so a reset shows.
fn loco() -> Loco {
    let mut loco = Loco::new(Decoder::new(DccShort, 100, 128).unwrap(), 100.0).unwrap();
    loco.speed_curve.add_point(50.0, 20.0);
    loco
}

fn straight(max_speed: f64, max_steps: f64) -> Vec<(f64, f64)> {
    vec![(0.0, 0.0), (max_speed, max_steps)]
}

#[test]
fn new_starts_with_a_straight_curve() {
    let loco = Loco::new(Decoder::new(Motorola2, 1, 28).unwrap(), 80.0).unwrap();
    assert_eq!(loco.speed_curve().points(), straight(80.0, 28.0));
}

#[test]
fn new_rejects_max_speed_out_of_range() {
    let decoder = Decoder::new(DccShort, 1, 128).unwrap();
    for max_speed in [0.5, 999.5, f64::NAN] {
        assert_eq!(
            Loco::new(decoder, max_speed),
            Err(LocoError::MaxSpeedOutOfRange)
        );
    }
}

#[test]
fn confirmed_max_speed_resets_the_curve() {
    let mut loco = loco();
    loco.set_max_speed(120.0, true).unwrap();
    assert_eq!(loco.max_speed(), 120.0);
    assert_eq!(loco.speed_curve().points(), straight(120.0, 128.0));
}

#[test]
fn confirmed_speed_steps_reset_the_curve() {
    let mut loco = loco();
    loco.set_speed_steps(28, true).unwrap();
    assert_eq!(loco.decoder().speed_steps(), 28);
    assert_eq!(loco.speed_curve().points(), straight(100.0, 28.0));
}

#[test]
fn confirmed_protocol_resets_the_curve() {
    let mut loco = loco();
    loco.set_speed_steps(28, true).unwrap();
    loco.speed_curve.add_point(50.0, 5.0);
    loco.set_protocol(Motorola1, true).unwrap();
    assert_eq!(Decoder::new(Motorola1, 80, 14).as_ref(), Ok(loco.decoder()));
    assert_eq!(loco.speed_curve().points(), straight(100.0, 14.0));
}

#[test]
fn unconfirmed_changes_leave_the_loco_unchanged() {
    let mut loco = loco();
    let before = loco.clone();
    assert_eq!(
        loco.set_max_speed(120.0, false),
        Err(LocoError::ResetNotConfirmed)
    );
    assert_eq!(
        loco.set_speed_steps(28, false),
        Err(LocoError::ResetNotConfirmed)
    );
    assert_eq!(
        loco.set_protocol(Motorola1, false),
        Err(LocoError::ResetNotConfirmed)
    );
    assert_eq!(loco, before);
}

#[test]
fn unchanged_values_keep_the_curve_without_confirmation() {
    let mut loco = loco();
    let before = loco.clone();
    loco.set_max_speed(100.0, false).unwrap();
    loco.set_speed_steps(128, false).unwrap();
    loco.set_protocol(DccShort, false).unwrap();
    assert_eq!(loco, before);
}

#[test]
fn invalid_changes_fail_before_asking_for_confirmation() {
    let mut loco = loco();
    let before = loco.clone();
    assert_eq!(
        loco.set_max_speed(0.0, false),
        Err(LocoError::MaxSpeedOutOfRange)
    );
    assert!(matches!(
        loco.set_speed_steps(27, false),
        Err(LocoError::Decoder(
            DecoderError::SpeedStepsNotSupported { .. }
        ))
    ));
    assert_eq!(loco, before);
}

#[test]
fn address_changes_keep_the_curve() {
    let mut loco = loco();
    let curve = loco.speed_curve().clone();
    loco.set_address(127).unwrap();
    assert_eq!(loco.decoder().address(), 127);
    assert!(loco.set_address(128).is_err());
    assert_eq!(loco.speed_curve(), &curve);
}

#[test]
fn new_has_the_durations_and_volume_of_electrip_1() {
    let loco = loco();
    assert_eq!(loco.accel_duration(), 11.5);
    assert_eq!(loco.brake_duration(), 8.5);
    assert_eq!(loco.volume(), 0.8);
}

#[test]
fn durations_and_volume_change_without_resetting_the_curve() {
    let mut loco = loco();
    let curve = loco.speed_curve().clone();
    loco.set_accel_duration(1.0).unwrap();
    loco.set_brake_duration(9999.0).unwrap();
    loco.set_volume(0.0).unwrap();
    assert_eq!(
        (loco.accel_duration(), loco.brake_duration(), loco.volume()),
        (1.0, 9999.0, 0.0)
    );
    assert_eq!(*loco.speed_curve(), curve);
}

#[test]
fn durations_and_volume_out_of_range_change_nothing() {
    let mut loco = loco();
    let before = loco.clone();
    for seconds in [0.5, 9999.5, f64::NAN] {
        assert_eq!(
            loco.set_accel_duration(seconds),
            Err(LocoError::DurationOutOfRange)
        );
        assert_eq!(
            loco.set_brake_duration(seconds),
            Err(LocoError::DurationOutOfRange)
        );
    }
    for volume in [-0.1, 1.1, f64::NAN] {
        assert_eq!(loco.set_volume(volume), Err(LocoError::VolumeOutOfRange));
    }
    assert_eq!(loco, before);
}

#[test]
fn a_new_loco_has_no_sound() {
    let mut loco = loco();
    assert_eq!(loco.sound_model(), None);
    assert_eq!(loco.insert_segment(0), Err(LocoError::NoSound));
    assert_eq!(loco.move_segment_border(0, 1.0), Err(LocoError::NoSound));
    assert_eq!(loco.remove_segment(0, true), Err(LocoError::NoSound));
}

#[test]
fn replacing_the_sound_model_needs_a_confirmation() {
    let mut loco = loco();
    loco.set_engine(Some(Engine::Diesel), false).unwrap();
    loco.insert_segment(0).unwrap();
    let before = loco.clone();
    for engine in [Some(Engine::Steam), None] {
        let error = loco.set_engine(engine, false);
        assert_eq!(error, Err(LocoError::SoundResetNotConfirmed));
        assert_eq!(loco, before);
    }
    loco.set_engine(Some(Engine::Diesel), false).unwrap();
    assert_eq!(loco, before);

    loco.set_engine(Some(Engine::Steam), true).unwrap();
    assert_eq!(loco.sound_model(), Some(&SoundModel::new(Engine::Steam)));
    loco.set_engine(None, true).unwrap();
    assert_eq!(loco.sound_model(), None);
}

#[test]
fn removing_the_last_segment_needs_a_confirmation() {
    let mut loco = loco();
    loco.set_engine(Some(Engine::Diesel), false).unwrap();
    loco.insert_segment(0).unwrap();
    loco.remove_segment(0, false).unwrap();
    assert_eq!(loco.sound_model().unwrap().segments().len(), 1);

    let before = loco.clone();
    assert_eq!(
        loco.remove_segment(1, true),
        Err(LocoError::UnknownSegment(1))
    );
    assert_eq!(
        loco.remove_segment(0, false),
        Err(LocoError::SoundResetNotConfirmed)
    );
    assert_eq!(loco, before);
    loco.remove_segment(0, true).unwrap();
    assert_eq!(loco.sound_model(), None);
}

#[test]
fn a_new_max_speed_stretches_the_segments() {
    let mut loco = loco();
    loco.set_engine(Some(Engine::Steam), false).unwrap();
    loco.insert_segment(0).unwrap();
    loco.move_segment_border(1, 20.0).unwrap();
    loco.set_max_speed(150.0, true).unwrap();
    let starts: Vec<f64> = loco
        .sound_model()
        .unwrap()
        .segments()
        .iter()
        .map(|s| s.start)
        .collect();
    assert_eq!(starts, [0.0, 30.0]);
}
