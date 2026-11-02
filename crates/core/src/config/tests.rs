use super::*;
use crate::decoder::{Decoder, Protocol};
use crate::function::Function;
use crate::input::Target;
use tempfile::TempDir;

#[test]
fn names_must_be_file_names_on_every_platform() {
    for name in ["Anlage", "Anlage 2", "Bf. Süd", "Keller (alt)"] {
        assert!(valid_name(name), "{name}");
    }
    for name in [
        "", ".hidden", "..", "a/b", "a\\b", "C:", "a?", "end ", "tab\t",
    ] {
        assert!(!valid_name(name), "{name:?}");
    }
}

#[test]
fn a_written_config_reads_back_equal() {
    let mut loco = Loco::new(Decoder::new(Protocol::DccLong, 1234, 28).unwrap(), 120.0).unwrap();
    loco.set_name("BR 216".into());
    loco.speed_curve_mut().add_point(60.0, 10.0);
    loco.functions_mut().push(Function {
        action: 3,
        number: 4,
        name: "Horn".into(),
        mode: Default::default(),
        default_on: true,
        on: true,
    });
    let mut mapping = Mapping::new("Xbox".into());
    mapping.bind("x".into(), Target::Action { action: 3 });
    let config = Config {
        locos: vec![loco],
        actions: vec![Action {
            id: 3,
            name: "Horn".into(),
        }],
        mappings: vec![mapping],
        station: Station {
            host: "srcp".into(),
            power_on_start: false,
            ..Station::default()
        },
    };
    let dir = TempDir::new().unwrap();
    let path = path(dir.path(), "Anlage");
    write(&path, &config).unwrap();
    assert_eq!(read(&path).unwrap(), config);
}

#[test]
fn names_lists_only_json_files_sorted() {
    let dir = TempDir::new().unwrap();
    for file in ["b.json", "a.json", "notes.txt"] {
        fs::write(dir.path().join(file), "{}").unwrap();
    }
    assert_eq!(names(dir.path()).unwrap(), ["a", "b"]);
}

#[test]
fn reading_an_invalid_file_fails() {
    let dir = TempDir::new().unwrap();
    let path = path(dir.path(), "kaputt");
    fs::write(&path, "{\"locos\": 1}").unwrap();
    assert!(read(&path).is_err());
}

#[test]
fn names_leaves_out_invalid_names() {
    let dir = TempDir::new().unwrap();
    for file in ["a.json", "end .json", "a.json.tmp"] {
        fs::write(dir.path().join(file), "{}").unwrap();
    }
    assert_eq!(names(dir.path()).unwrap(), ["a"]);
}
