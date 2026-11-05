use super::*;

fn starts(model: &SoundModel) -> Vec<f64> {
    model.segments().iter().map(|s| s.start).collect()
}

/// A model with segments starting at 0, 40 and 80 km/h.
fn three_segments() -> SoundModel {
    let mut model = SoundModel::new(Engine::Diesel);
    model.insert_segment(0, 80.0).unwrap();
    model.insert_segment(1, 120.0).unwrap();
    model
}

#[test]
fn a_new_model_has_one_segment_from_standstill() {
    assert_eq!(starts(&SoundModel::new(Engine::Steam)), [0.0]);
}

#[test]
fn inserting_splits_the_segment_in_the_middle() {
    let mut model = three_segments();
    assert_eq!(starts(&model), [0.0, 40.0, 80.0]);
    model.insert_segment(2, 120.0).unwrap();
    model.insert_segment(0, 120.0).unwrap();
    assert_eq!(starts(&model), [0.0, 20.0, 40.0, 80.0, 100.0]);
}

#[test]
fn removing_gives_the_speeds_to_the_left_neighbour() {
    let mut model = three_segments();
    model.remove_segment(1).unwrap();
    assert_eq!(starts(&model), [0.0, 80.0]);
    model.remove_segment(1).unwrap();
    assert_eq!(starts(&model), [0.0]);
}

#[test]
fn removing_the_first_gives_its_speeds_to_the_right_neighbour() {
    let mut model = three_segments();
    model.remove_segment(0).unwrap();
    assert_eq!(starts(&model), [0.0, 80.0]);
}

#[test]
fn a_border_moves_only_between_its_neighbours() {
    let mut model = three_segments();
    model.move_border(1, 30.0, 120.0).unwrap();
    model.move_border(2, 110.0, 120.0).unwrap();
    assert_eq!(starts(&model), [0.0, 30.0, 110.0]);
    for (nr, speed) in [(0, 10.0), (1, 0.0), (1, 110.0), (2, 120.0), (2, 20.0)] {
        model.move_border(nr, speed, 120.0).unwrap();
    }
    assert_eq!(starts(&model), [0.0, 30.0, 110.0]);
}

#[test]
fn unknown_segments_are_errors() {
    let mut model = three_segments();
    let before = model.clone();
    assert_eq!(
        model.insert_segment(3, 120.0),
        Err(LocoError::UnknownSegment(3))
    );
    assert_eq!(model.remove_segment(3), Err(LocoError::UnknownSegment(3)));
    assert_eq!(
        model.move_border(3, 1.0, 120.0),
        Err(LocoError::UnknownSegment(3))
    );
    assert_eq!(model, before);
}

#[test]
fn strokes_follow_the_turn_of_the_wheels_down_to_the_minimum_frequency() {
    let steam = Steam::default();
    // 1.2 m wheels at 36 km/h turn in 1.2 π / 10 s, split into 4 strokes.
    let pause = steam.pause(36.0).as_secs_f64();
    assert!((pause - 0.03 * PI).abs() < 1e-9, "{pause}");
    assert_eq!(steam.pause(0.1), Duration::from_secs(5));
}

#[test]
fn steam_values_out_of_range_are_errors() {
    let mut model = SoundModel::new(Engine::Steam);
    for steam in [
        Steam {
            strokes: 0,
            ..Steam::default()
        },
        Steam {
            wheel_diameter: 0.0,
            ..Steam::default()
        },
        Steam {
            start_delay: -1.0,
            ..Steam::default()
        },
        Steam {
            min_frequency: 0.0,
            ..Steam::default()
        },
    ] {
        assert_eq!(model.set_steam(steam), Err(LocoError::SteamOutOfRange));
    }
    assert_eq!(model.steam(), &Steam::default());
}

#[test]
fn stroke_sounds_exist_only_for_the_strokes() {
    let mut model = SoundModel::new(Engine::Steam);
    let path = || Some(PathBuf::from("a"));
    model.set_stroke_sound(0, 3, path()).unwrap();
    assert_eq!(model.stroke_sound(0, 3), Some(Path::new("a")));
    assert_eq!(
        model.set_stroke_sound(0, 4, path()),
        Err(LocoError::UnknownStroke(4))
    );
    assert_eq!(
        model.set_stroke_sound(1, 0, path()),
        Err(LocoError::UnknownSegment(1))
    );
}
