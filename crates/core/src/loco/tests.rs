use super::*;
use crate::decoder::Protocol::*;

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
