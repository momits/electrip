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
