use super::*;
use crate::decoder::{Decoder, Protocol};

const DEAD_ZONE: f64 = 0.06;

/// 100 km/h, 11.5 s to accelerate, 8.5 s to brake.
fn loco() -> Loco {
    Loco::new(Decoder::new(Protocol::DccShort, 1, 128).unwrap(), 100.0).unwrap()
}

/// Seconds until the speed reaches `target`, in ticks of 50 ms as in
/// Electrip 1.
fn time_to(motion: &mut Motion, deflection: f64, target: f64) -> f64 {
    let loco = loco();
    let mut seconds = 0.0;
    while motion.speed() != target && seconds < 100.0 {
        motion.accelerate(&loco, deflection, DEAD_ZONE, 0.05);
        seconds += 0.05;
    }
    seconds
}

fn moving(speed: f64) -> Motion {
    Motion {
        speed,
        forward: true,
    }
}

fn assert_near(actual: f64, expected: f64) {
    assert!(
        (actual - expected).abs() <= expected * 0.1,
        "{actual} is not within 10 % of {expected}"
    );
}

#[test]
fn starts_at_standstill_forward() {
    assert_eq!(Motion::default(), moving(0.0));
}

#[test]
fn full_forward_reaches_max_speed_in_the_acceleration_duration() {
    assert_near(time_to(&mut Motion::default(), 1.0, 100.0), 11.5);
}

#[test]
fn full_back_stops_from_max_speed_in_the_braking_duration() {
    assert_near(time_to(&mut moving(100.0), -1.0, 0.0), 8.5);
}

#[test]
fn acceleration_is_proportional_to_the_deflection() {
    let (mut half, mut full) = (moving(50.0), moving(50.0));
    half.accelerate(&loco(), 0.5, DEAD_ZONE, 1.0);
    full.accelerate(&loco(), 1.0, DEAD_ZONE, 1.0);
    assert_eq!(full.speed() - 50.0, 2.0 * (half.speed() - 50.0));
    let (mut half, mut full) = (moving(50.0), moving(50.0));
    half.accelerate(&loco(), -0.5, DEAD_ZONE, 1.0);
    full.accelerate(&loco(), -1.0, DEAD_ZONE, 1.0);
    assert_eq!(50.0 - full.speed(), 2.0 * (50.0 - half.speed()));
}

#[test]
fn axis_within_the_dead_zone_keeps_the_speed() {
    for deflection in [0.0, DEAD_ZONE, -DEAD_ZONE] {
        let mut motion = moving(50.0);
        motion.accelerate(&loco(), deflection, DEAD_ZONE, 1.0);
        assert_eq!(motion, moving(50.0));
    }
}

#[test]
fn speed_stays_between_standstill_and_max_speed() {
    let mut motion = moving(99.0);
    motion.accelerate(&loco(), 1.0, DEAD_ZONE, 10.0);
    assert_eq!(motion.speed(), 100.0);
    motion.accelerate(&loco(), -1.0, DEAD_ZONE, 100.0);
    assert_eq!(motion.speed(), 0.0);
}

#[test]
fn reverse_stops_and_changes_the_direction() {
    let mut motion = moving(50.0);
    motion.reverse();
    assert_eq!(
        motion,
        Motion {
            speed: 0.0,
            forward: false
        }
    );
    motion.reverse();
    assert_eq!(motion, moving(0.0));
}
