use super::*;
use crate::decoder::Protocol;
use crate::event_sound::EventSound;
use crate::function::Function;
use crate::sound::SegmentSound;
use image::RgbImage;
use std::path::PathBuf;
use tempfile::TempDir;

fn corpus(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("../../tests/corpus/packages/{name}.zip"))
}

/// A ZIP archive at `path` with the files `(name, content)`.
fn archive(path: &Path, files: &[(&str, &[u8])]) {
    let mut zip = ZipWriter::new(File::create(path).unwrap());
    for (name, content) in files {
        zip.start_file(*name, SimpleFileOptions::default()).unwrap();
        zip.write_all(content).unwrap();
    }
    zip.finish().unwrap();
}

/// The sound files of the loco.
fn sounds(loco: &Loco) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    loco.clone().map_sounds(|path| {
        paths.push(path.to_owned());
        None
    });
    paths
}

fn png() -> Vec<u8> {
    let mut png = Vec::new();
    RgbImage::new(220, 170)
        .write_to(&mut io::Cursor::new(&mut png), image::ImageFormat::Png)
        .unwrap();
    png
}

#[test]
fn the_packages_of_electrip_1_are_imported() {
    let library = TempDir::new().unwrap();
    let names = ["BR 216", "BR 81", "Koef II", "V 200", "V 60", "VT 98"];
    for name in names {
        let package = read(&corpus(name), library.path()).unwrap();
        assert_eq!(package.loco.name(), name);
        assert_eq!(package.report, Vec::<String>::new(), "{name}");
        let picture = package.loco.picture().unwrap();
        assert!(picture::path(library.path(), picture).exists(), "{name}");
    }
    let br_216 = read(&corpus("BR 216"), library.path()).unwrap().loco;
    assert_eq!(br_216.decoder().protocol(), Protocol::DccShort);
    assert_eq!(br_216.decoder().address(), 2);
    assert_eq!(br_216.max_speed(), 120.00000000000003);
    assert_eq!(br_216.accel_duration(), 20.0);
    assert_eq!(br_216.brake_duration(), 17.0);
    let koef = read(&corpus("Koef II"), library.path()).unwrap().loco;
    assert_eq!(koef.decoder().protocol(), Protocol::Motorola2);
}

#[test]
fn the_sounds_of_electrip_1_are_saved_in_the_library() {
    let library = TempDir::new().unwrap();
    let names = ["BR 216", "BR 81", "Koef II", "V 200", "V 60", "VT 98"];
    for name in names {
        let loco = read(&corpus(name), library.path()).unwrap().loco;
        assert!(!sounds(&loco).is_empty(), "{name}");
        for path in sounds(&loco) {
            assert_eq!(path.parent(), Some(Path::new(media::SOUNDS)), "{name}");
            assert!(library.path().join(&path).exists(), "{name}: {path:?}");
        }
    }
    let loco = read(&corpus("V 60"), library.path()).unwrap().loco;
    let path = loco
        .sound_model()
        .unwrap()
        .segment_sound(0, SegmentSound::Accel);
    let mut zip = ZipArchive::new(File::open(corpus("V 60")).unwrap()).unwrap();
    let original = entry(&mut zip, "sound/FS0-FS1.ogg").unwrap();
    assert_eq!(
        fs::read(library.path().join(path.unwrap())).unwrap(),
        original
    );
    let brake = loco.event_sounds()[0].path.as_ref().unwrap();
    let original = entry(&mut zip, "sound/Bremse1.ogg").unwrap();
    assert_eq!(fs::read(library.path().join(brake)).unwrap(), original);
}

#[test]
fn the_functions_of_electrip_1_get_actions() {
    let library = TempDir::new().unwrap();
    let package = read(&corpus("VT 98"), library.path()).unwrap();
    let names: Vec<_> = package.actions.iter().map(|a| a.name.as_str()).collect();
    let buttons = (0..=5).map(|nr| format!("Knopf {nr}"));
    let expected: Vec<String> = ["Knopf 6", "Knopf 7", "ABV Aus"]
        .map(String::from)
        .into_iter()
        .chain(buttons)
        .collect();
    assert_eq!(names, expected);
    let sounds = package.loco.sound_functions();
    let ids: Vec<_> = sounds.iter().map(|f| f.action).collect();
    assert_eq!(ids, [4, 5, 6, 7, 8, 9]);
    let functions = package.loco.functions();
    let ids: Vec<_> = functions.iter().map(|f| f.action).collect();
    assert_eq!(ids, [1, 2, 3]);
    assert_eq!(
        (functions[0].name.as_str(), functions[0].number),
        ("Licht", 0)
    );
    assert!(functions[0].default_on && functions[0].on);
    assert_eq!(
        (functions[1].name.as_str(), functions[1].number),
        ("Rangiergang", 3)
    );
}

#[test]
fn an_exported_loco_is_imported_again() {
    let dir = TempDir::new().unwrap();
    let library = dir.path().join("library");
    let source = dir.path().join("loco.png");
    fs::write(&source, png()).unwrap();
    let mut loco = read(&corpus("V 60"), &library).unwrap().loco;
    loco.set_picture(Some(picture::store(&library, &source, None).unwrap()));
    *loco.functions_mut() = vec![Function {
        action: 2,
        number: 0,
        name: "Licht".into(),
        mode: Default::default(),
        default_on: true,
        on: true,
    }];
    *loco.event_sounds_mut() = vec![EventSound {
        action: 3,
        name: "Quietschen".into(),
        max_accel: Some(-2.0),
        ..EventSound::default()
    }];
    let actions = [1, 2, 3].map(|id| Action {
        id,
        name: format!("Aktion {id}"),
    });
    let path = dir.path().join("V 60.zip");
    write(&path, &loco, &actions, &library).unwrap();

    let other = dir.path().join("other");
    let package = read(&path, &other).unwrap();
    for sound in sounds(&package.loco) {
        assert!(other.join(sound).exists());
    }
    assert_eq!(package.loco, loco);
    assert_eq!(package.actions, actions[1..]);
    assert_eq!(package.report, Vec::<String>::new());
    let picture = picture::path(&other, loco.picture().unwrap());
    assert_eq!(
        fs::read(picture).unwrap(),
        fs::read(picture::path(&library, loco.picture().unwrap())).unwrap()
    );
}

#[test]
fn a_missing_picture_is_reported() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().join("Lok.zip");
    let loco = br#"{"name": "Lok", "img_path": "image/lok.png", "speed_control_points": [[0, 0], [100, 128]]}"#;
    archive(&path, &[("Lok.loco", loco)]);
    let package = read(&path, dir.path()).unwrap();
    assert_eq!(package.loco.picture(), None);
    assert_eq!(package.report.len(), 1);
    assert!(
        package.report[0].starts_with("Lok: cannot read the file"),
        "{:?}",
        package.report
    );
}

#[test]
fn a_broken_picture_is_reported() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().join("Lok.zip");
    let loco = br#"{"name": "Lok", "img_path": "image/lok.png", "speed_control_points": [[0, 0], [100, 128]]}"#;
    archive(&path, &[("Lok.loco", loco), ("image/lok.png", b"no image")]);
    let package = read(&path, dir.path()).unwrap();
    assert_eq!(package.loco.picture(), None);
    assert!(
        package.report[0].starts_with("Lok: cannot read the picture"),
        "{:?}",
        package.report
    );
}

#[test]
fn a_missing_sound_is_reported_and_left_out() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().join("Lok.zip");
    let loco = br#"{"name": "Lok", "speed_control_points": [[0, 0], [100, 128]],
        "function_sounds": [{"name": "Horn", "button": 1, "file_path": "sound/horn.ogg"}]}"#;
    archive(&path, &[("Lok.loco", loco)]);
    let package = read(&path, dir.path()).unwrap();
    assert_eq!(package.loco.sound_functions()[0].path, None);
    assert_eq!(package.report.len(), 1);
    assert!(
        package.report[0].starts_with("Lok: cannot read the file")
            && package.report[0].ends_with("(sound/horn.ogg)"),
        "{:?}",
        package.report
    );
}

#[test]
fn a_loco_with_a_missing_sound_is_not_exported() {
    let dir = TempDir::new().unwrap();
    let mut loco = read(&corpus("VT 98"), dir.path()).unwrap().loco;
    loco.sound_functions_mut()[0].path = Some(dir.path().join("missing.ogg"));
    let path = dir.path().join("VT 98.zip");
    assert!(write(&path, &loco, &[], dir.path()).is_err());
}

#[test]
fn other_files_are_no_packages() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().join("Lok.zip");
    archive(&path, &[("sound/horn.ogg", b"")]);
    let error = read(&path, dir.path()).unwrap_err();
    assert_eq!(error, ImportError::Invalid("no loco file".into()));
    fs::write(&path, b"no zip").unwrap();
    assert!(matches!(read(&path, dir.path()), Err(ImportError::Read(_))));
    archive(&path, &[("loco.json", b"{}")]);
    assert!(matches!(
        read(&path, dir.path()),
        Err(ImportError::Invalid(_))
    ));
}
