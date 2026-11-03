use super::*;
use crate::decoder::Protocol;
use crate::function::Function;
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

fn png() -> Vec<u8> {
    let mut png = Vec::new();
    RgbImage::new(220, 170)
        .write_to(&mut io::Cursor::new(&mut png), image::ImageFormat::Png)
        .unwrap();
    png
}

#[test]
fn the_packages_of_electrip_1_are_imported() {
    let media = TempDir::new().unwrap();
    let names = ["BR 216", "BR 81", "Koef II", "V 200", "V 60", "VT 98"];
    for name in names {
        let package = read(&corpus(name), media.path()).unwrap();
        assert_eq!(package.loco.name(), name);
        assert_eq!(package.report, Vec::<String>::new(), "{name}");
        let picture = package.loco.picture().unwrap();
        assert!(picture::path(media.path(), picture).exists(), "{name}");
    }
    let br_216 = read(&corpus("BR 216"), media.path()).unwrap().loco;
    assert_eq!(br_216.decoder().protocol(), Protocol::DccShort);
    assert_eq!(br_216.decoder().address(), 2);
    assert_eq!(br_216.max_speed(), 120.00000000000003);
    assert_eq!(br_216.accel_duration(), 20.0);
    assert_eq!(br_216.brake_duration(), 17.0);
    let koef = read(&corpus("Koef II"), media.path()).unwrap().loco;
    assert_eq!(koef.decoder().protocol(), Protocol::Motorola2);
}

#[test]
fn the_functions_of_electrip_1_get_actions() {
    let media = TempDir::new().unwrap();
    let package = read(&corpus("VT 98"), media.path()).unwrap();
    let names: Vec<_> = package.actions.iter().map(|a| a.name.as_str()).collect();
    assert_eq!(names, ["Knopf 6", "Knopf 7", "ABV Aus"]);
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
    let media = dir.path().join("media");
    let source = dir.path().join("loco.png");
    fs::write(&source, png()).unwrap();
    let mut loco = read(&corpus("V 60"), &media).unwrap().loco;
    loco.set_picture(Some(picture::store(&media, &source, None).unwrap()));
    *loco.functions_mut() = vec![Function {
        action: 2,
        number: 0,
        name: "Licht".into(),
        mode: Default::default(),
        default_on: true,
        on: true,
    }];
    let actions = [1, 2].map(|id| Action {
        id,
        name: format!("Aktion {id}"),
    });
    let path = dir.path().join("V 60.zip");
    write(&path, &loco, &actions, &media).unwrap();

    let other_media = dir.path().join("other");
    let package = read(&path, &other_media).unwrap();
    assert_eq!(package.loco, loco);
    assert_eq!(package.actions, [actions[1].clone()]);
    assert_eq!(package.report, Vec::<String>::new());
    let picture = picture::path(&other_media, loco.picture().unwrap());
    assert_eq!(
        fs::read(picture).unwrap(),
        fs::read(picture::path(&media, loco.picture().unwrap())).unwrap()
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
