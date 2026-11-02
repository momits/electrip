//! B-08: the speed curve gives the same points and speed steps as Electrip 1
//! (`tests/golden/speed_curve.jsonl`, recorded from the scenario).

use electrip_core::speed_curve::{Point, SpeedCurve};
use serde_json::Value;
use std::fs;

#[test]
fn speed_curve_matches_electrip_1() {
    let read = |path: &str| {
        fs::read_to_string(format!("{}/../../{path}", env!("CARGO_MANIFEST_DIR"))).unwrap()
    };
    let points = |value: &Value| -> Vec<Point> {
        let pair = |p: &Value| (p[0].as_f64().unwrap(), p[1].as_f64().unwrap());
        value.as_array().unwrap().iter().map(pair).collect()
    };
    let scenario: Value =
        serde_json::from_str(&read("tests/golden/scenarios/speed_curve.json")).unwrap();
    let curves: Vec<SpeedCurve> = scenario["curves"]
        .as_array()
        .unwrap()
        .iter()
        .map(|c| SpeedCurve::new(&points(&c["points"])).unwrap())
        .collect();
    for line in read("tests/golden/speed_curve.jsonl").lines() {
        let entry: Value = serde_json::from_str(line).unwrap();
        let curve = &curves[entry["curve"].as_u64().unwrap() as usize];
        if entry["points"].is_array() {
            assert_eq!(curve.points(), points(&entry["points"]), "{line}");
        } else {
            let step = curve.step_at(entry["x"].as_f64().unwrap());
            assert_eq!(step, entry["step"].as_f64(), "{line}");
        }
    }
}
