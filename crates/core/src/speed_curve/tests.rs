use super::*;

fn curve() -> SpeedCurve {
    SpeedCurve::new(&[(0.0, 2.0), (50.0, 60.0), (100.0, 128.0)]).unwrap()
}

#[test]
fn new_needs_two_points_spanning_a_speed() {
    assert!(SpeedCurve::new(&[]).is_none());
    assert!(SpeedCurve::new(&[(0.0, 0.0)]).is_none());
    assert!(SpeedCurve::new(&[(100.0, 0.0), (0.0, 128.0)]).is_none());
    assert!(SpeedCurve::new(&[(0.0, 0.0), (100.0, 128.0)]).is_some());
}

#[test]
fn step_interpolates_between_points() {
    let c = curve();
    for (speed, step) in [(25.0, 31.0), (50.0, 60.0), (75.0, 94.0), (100.0, 128.0)] {
        assert!((c.step_at(speed).unwrap() - step).abs() < 1e-9, "{speed}");
    }
}

#[test]
fn speed_zero_is_step_zero_and_outside_is_none() {
    let c = curve();
    assert_eq!(c.step_at(0.0), Some(0.0));
    assert_eq!(c.step_at(-1.0), None);
    assert_eq!(c.step_at(100.5), None);
}

#[test]
fn add_point_keeps_the_curve_rising() {
    let mut c = curve();
    c.add_point(10.0, 100.0);
    c.add_point(90.0, 1.0);
    assert_eq!(
        c.points(),
        [
            (0.0, 2.0),
            (10.0, 60.0),
            (50.0, 60.0),
            (90.0, 60.0),
            (100.0, 128.0)
        ]
    );
}

#[test]
fn add_point_ignores_existing_speeds_and_outside() {
    let mut c = curve();
    for speed in [0.0, 50.0, 100.0, -5.0, 120.0] {
        c.add_point(speed, 10.0);
    }
    assert_eq!(c, curve());
}

#[test]
fn first_and_last_point_cannot_be_removed() {
    let mut c = curve();
    c.remove_point(0);
    c.remove_point(2);
    c.remove_point(7);
    assert_eq!(c, curve());
    c.remove_point(1);
    assert_eq!(c.points(), [(0.0, 2.0), (100.0, 128.0)]);
}

#[test]
fn ends_move_only_their_step_within_the_neighbour() {
    let mut c = curve();
    c.move_point(0, 30.0, 90.0);
    c.move_point(2, 80.0, 10.0);
    assert_eq!(c.points(), [(0.0, 60.0), (50.0, 60.0), (100.0, 60.0)]);
}

#[test]
fn inner_point_moves_between_its_neighbours() {
    let mut c = curve();
    c.move_point(1, 70.0, 200.0);
    assert_eq!(c.points()[1], (70.0, 128.0));
    c.move_point(1, 100.0, 50.0);
    c.move_point(1, 0.0, 50.0);
    assert_eq!(c.points()[1], (70.0, 128.0));
    c.move_point(5, 50.0, 50.0);
    assert_eq!(c.points().len(), 3);
}

#[test]
fn right_neighbour_wins_on_a_falling_curve_like_electrip_1() {
    let mut c = SpeedCurve::new(&[(0.0, 100.0), (100.0, 0.0)]).unwrap();
    c.add_point(50.0, 30.0);
    c.move_point(1, 50.0, 200.0);
    assert_eq!(c.points()[1], (50.0, 0.0));
}

#[test]
fn the_speed_of_a_step_gives_the_step_back() {
    let curve = SpeedCurve::new(&[(0.0, 2.0), (30.0, 10.0), (60.0, 10.0), (100.0, 28.0)]).unwrap();
    assert_eq!(curve.speed_of_step(0), 0.0);
    for step in 2..=28 {
        let speed = curve.speed_of_step(step);
        let back = curve.step_at(speed).unwrap() as u8;
        assert_eq!(back, step, "step {step} at {speed} km/h");
    }
    assert_eq!(curve.speed_of_step(28), 100.0);
    assert_eq!(curve.speed_of_step(1), 0.0);
}
