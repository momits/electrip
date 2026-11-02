use super::*;
use serde_json::json;

#[test]
fn the_standard_mapping_follows_electrip_1() {
    let mapping = Mapping::new("pad".into());
    let drive = Target::Drive { dead_zone: 0.06 };
    assert_eq!(mapping.target("lefty"), Some(&drive));
    assert_eq!(mapping.target("a"), Some(&Target::TogglePower));
    assert_eq!(mapping.target("b"), Some(&Target::Reverse));
    assert_eq!(mapping.target("dpleft"), Some(&Target::PreviousLoco));
    assert_eq!(mapping.target("dpright"), Some(&Target::NextLoco));
    assert_eq!(mapping.target("x"), None);
}

#[test]
fn binding_a_control_replaces_its_target() {
    let mut mapping = Mapping::new("pad".into());
    mapping.bind("a".into(), Target::Action { action: 1 });
    assert_eq!(mapping.target("a"), Some(&Target::Action { action: 1 }));
    assert_eq!(mapping.bindings.len(), 5);
    mapping.unbind("a");
    assert_eq!(mapping.target("a"), None);
}

#[test]
fn targets_read_from_json() {
    let targets: Vec<Target> = serde_json::from_value(json!([
        {"type": "drive"},
        {"type": "drive", "dead_zone": 0.2},
        {"type": "emergency_stop"},
        {"type": "action", "action": 3},
    ]))
    .unwrap();
    assert_eq!(
        targets,
        [
            Target::Drive { dead_zone: 0.06 },
            Target::Drive { dead_zone: 0.2 },
            Target::EmergencyStop,
            Target::Action { action: 3 },
        ]
    );
}

#[test]
fn a_device_reports_only_changes_of_its_buttons() {
    let mut device = Device::new(1, "pad".into());
    assert!(device.press("a", true));
    assert!(!device.press("a", true));
    assert!(device.press("b", true));
    assert!(device.press("a", false));
    assert!(!device.press("a", false));
}
