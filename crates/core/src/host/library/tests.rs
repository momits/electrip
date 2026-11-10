use super::*;
use crate::audio::tests::LogSink;
use crate::function::Function;
use crate::host::Connector;
use crate::host::tests::{host, set_server};
use crate::session::Command;
use crate::station::StationError;
use std::sync::Arc;
use tempfile::TempDir;

fn corpus(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("../../tests/corpus/configs/{name}.json"))
}

fn names(host: &Host) -> Vec<String> {
    config::names(&host.library).unwrap()
}

fn new_configuration(host: &mut Host, name: &str) -> Result<(), CommandError> {
    host.apply(Command::NewConfiguration { name: name.into() })
}

fn open(host: &mut Host, name: &str) -> Result<(), CommandError> {
    host.apply(Command::OpenConfiguration { name: name.into() })
}

fn loco_names(host: &Host) -> Vec<&str> {
    let locos = host.session().locos();
    locos.iter().map(|e| e.loco.name()).collect()
}

#[test]
fn an_empty_library_gets_a_configuration() {
    let (host, _, _, _library) = host();
    assert_eq!(host.session().configuration(), DEFAULT_NAME);
    assert_eq!(names(&host), [DEFAULT_NAME]);
}

#[test]
fn every_change_is_saved_and_opened_again() {
    let (mut host, _, _, library) = host();
    for name in ["Ae 6/6", "V 60"] {
        host.apply(Command::AddLoco).unwrap();
        let loco = host.session().locos().last().unwrap().id;
        let name = name.into();
        host.apply(Command::RenameLoco { loco, name }).unwrap();
    }
    host.apply(Command::MoveLoco {
        loco: 2,
        position: 0,
    })
    .unwrap();
    host.apply(Command::AddAction {
        name: "Licht".into(),
    })
    .unwrap();
    let function = Function {
        action: 1,
        number: 0,
        name: "Licht".into(),
        mode: Default::default(),
        default_on: false,
        on: false,
    };
    host.apply(Command::AddFunction { loco: 1, function })
        .unwrap();
    set_server(&mut host, "srcp").unwrap();
    let config = host.session().config();

    let connect: Connector = Box::new(|_| Err(StationError("offline".into())));
    let reopened = Host::new(connect, Box::new(LogSink::default()), library.path().into()).unwrap();
    assert_eq!(reopened.session().config(), config);
    assert_eq!(loco_names(&reopened), ["V 60", "Ae 6/6"]);
    assert_eq!(reopened.session().station().host, "srcp");
}

#[test]
fn functions_are_saved_in_their_default_state() {
    let (mut host, _, _, _library) = host();
    host.apply(Command::AddLoco).unwrap();
    host.apply(Command::AddAction {
        name: "Licht".into(),
    })
    .unwrap();
    let function = Function {
        action: 1,
        number: 0,
        name: String::new(),
        mode: Default::default(),
        default_on: false,
        on: false,
    };
    host.apply(Command::AddFunction { loco: 1, function })
        .unwrap();
    host.apply(Command::TriggerAction {
        loco: 1,
        action: 1,
        pressed: true,
    })
    .unwrap();
    assert!(host.session().locos()[0].loco.functions()[0].on);
    let saved = config::read(&host.path(DEFAULT_NAME).unwrap()).unwrap();
    assert!(!saved.locos[0].functions()[0].on);
}

#[test]
fn new_configurations_start_empty_and_can_be_switched() {
    let (mut host, _, _, _library) = host();
    host.apply(Command::AddLoco).unwrap();
    let id = host.session().config().id;
    new_configuration(&mut host, "Keller").unwrap();
    assert_ne!(host.session().config().id, id);
    assert_eq!(host.session().configuration(), "Keller");
    assert!(host.session().locos().is_empty());
    assert_eq!(names(&host), [DEFAULT_NAME, "Keller"]);
    open(&mut host, DEFAULT_NAME).unwrap();
    assert_eq!(host.session().locos().len(), 1);
    // Ids are not reused after switching.
    assert_eq!(host.session().locos()[0].id, 2);
}

#[test]
fn names_must_be_new_and_valid() {
    let (mut host, _, _, _library) = host();
    let exists = Err(CommandError::ConfigurationExists(DEFAULT_NAME.into()));
    assert_eq!(new_configuration(&mut host, DEFAULT_NAME), exists);
    let invalid = Err(CommandError::InvalidName("../x".into()));
    assert_eq!(new_configuration(&mut host, "../x"), invalid);
    assert_eq!(open(&mut host, "../x"), invalid);
    assert!(matches!(
        open(&mut host, "fehlt"),
        Err(CommandError::File(_))
    ));
    assert_eq!(names(&host), [DEFAULT_NAME]);
}

#[test]
fn switching_needs_a_disconnected_host() {
    let (mut host, _, _, _library) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    let path = corpus("settings");
    let connected = Err(CommandError::Connected);
    assert_eq!(new_configuration(&mut host, "Keller"), connected);
    assert_eq!(open(&mut host, DEFAULT_NAME), connected);
    assert_eq!(host.apply(Command::ImportElectrip1 { path }), connected);
    assert_eq!(names(&host), [DEFAULT_NAME]);
}

#[test]
fn rename_renames_the_open_configuration() {
    let (mut host, _, _, _library) = host();
    new_configuration(&mut host, "Keller").unwrap();
    let rename = |host: &mut Host, name: &str| {
        host.apply(Command::RenameConfiguration { name: name.into() })
    };
    let exists = Err(CommandError::ConfigurationExists(DEFAULT_NAME.into()));
    assert_eq!(rename(&mut host, DEFAULT_NAME), exists);
    let id = host.session().config().id;
    rename(&mut host, "Dachboden").unwrap();
    assert_eq!(host.session().config().id, id);
    assert_eq!(host.session().configuration(), "Dachboden");
    assert_eq!(names(&host), ["Dachboden", DEFAULT_NAME]);
    // Changes go to the renamed file.
    host.apply(Command::AddLoco).unwrap();
    let saved = config::read(&host.path("Dachboden").unwrap()).unwrap();
    assert_eq!(saved.locos.len(), 1);
}

#[test]
fn only_other_configurations_can_be_removed() {
    let (mut host, _, _, _library) = host();
    new_configuration(&mut host, "Keller").unwrap();
    let remove = |host: &mut Host, name: &str| {
        host.apply(Command::RemoveConfiguration { name: name.into() })
    };
    let open = Err(CommandError::ConfigurationOpen("Keller".into()));
    assert_eq!(remove(&mut host, "Keller"), open);
    remove(&mut host, DEFAULT_NAME).unwrap();
    assert_eq!(names(&host), ["Keller"]);
    assert_eq!(host.session().config().locos, []);
}

#[test]
fn export_writes_the_open_configuration() {
    let (mut host, _, _, library) = host();
    host.apply(Command::AddLoco).unwrap();
    let path = library.path().join("export.txt");
    let command = Command::ExportConfiguration { path: path.clone() };
    host.apply(command).unwrap();
    assert_eq!(config::read(&path).unwrap(), host.session().config());
}

#[test]
fn import_creates_a_configuration_named_like_the_file() {
    let (mut host, _, _, _library) = host();
    host.apply(Command::AddLoco).unwrap();
    let path = corpus("settings");
    host.apply(Command::ImportElectrip1 { path: path.clone() })
        .unwrap();
    assert_eq!(host.session().configuration(), "settings");
    assert_eq!(loco_names(&host), ["BR 216", "V 60"]);
    // Ids are not reused.
    let ids: Vec<u32> = host.session().locos().iter().map(|e| e.id).collect();
    assert_eq!(ids, [2, 3]);
    let station = host.session().station();
    assert_eq!(station.host, "192.168.0.111");
    assert_eq!((station.port, station.bus), (4304, 2));
    let actions: Vec<_> = host
        .session()
        .actions()
        .iter()
        .map(|a| a.name.as_str())
        .collect();
    assert_eq!(
        actions,
        [
            "Knopf 1",
            "Knopf 6",
            "Knopf 7",
            "Knopf 8",
            "Rangiergang",
            "ABV Aus",
            "Knopf 3",
            "Knopf 2",
            "Knopf 4",
            "Knopf 5",
            "Bremsen",
        ]
    );
    host.apply(Command::AddAction {
        name: "Horn".into(),
    })
    .unwrap();
    assert_eq!(host.session().actions()[10].id, 11);
    let saved = config::read(&host.path("settings").unwrap()).unwrap();
    assert_eq!(saved, host.session().config());
    let exists = Err(CommandError::ConfigurationExists("settings".into()));
    assert_eq!(host.apply(Command::ImportElectrip1 { path }), exists);
}

#[test]
fn new_device_types_get_a_copy_of_the_imported_mapping() {
    let (mut host, _, _, _library) = host();
    let add = |host: &mut Host, device, kind: &str| {
        let kind = kind.into();
        host.apply(Command::AddDevice { device, kind }).unwrap();
    };
    add(&mut host, 1, "Gamepad");
    host.apply(Command::ImportElectrip1 {
        path: corpus("packages"),
    })
    .unwrap();
    add(&mut host, 2, "Joystick");
    let mappings = host.session().mappings();
    let kinds: Vec<_> = mappings.iter().map(|m| m.kind.as_str()).collect();
    assert_eq!(kinds, [electrip1::KIND, "Gamepad", "Joystick"]);
    assert_eq!(mappings[1].bindings, mappings[0].bindings);
    assert_eq!(mappings[2].bindings, mappings[0].bindings);
}

#[test]
fn a_failed_import_changes_nothing() {
    let (mut host, _, _, _library) = host();
    host.apply(Command::AddLoco).unwrap();
    let before = host.session().clone();
    let path = PathBuf::from("/nonexistent/anlage.json");
    let result = host.apply(Command::ImportElectrip1 { path });
    assert!(matches!(result, Err(CommandError::Import(_))));
    assert_eq!(*host.session(), before);
    assert_eq!(names(&host), [DEFAULT_NAME]);
}

#[test]
fn a_failed_save_changes_nothing() {
    let (mut host, _, _, _library) = host();
    // A directory in place of the file makes saving fail.
    let path = host.path(DEFAULT_NAME).unwrap();
    fs::remove_file(&path).unwrap();
    fs::create_dir(path.with_extension("json.tmp")).unwrap();
    let before = host.session().clone();
    let result = host.apply(Command::AddLoco);
    assert!(matches!(result, Err(CommandError::File(_))), "{result:?}");
    assert_eq!(*host.session(), before);
}

/// A PNG of `width`×`height` in one colour at `path`.
fn image_file(path: &Path, width: u32, height: u32) {
    image::RgbImage::from_pixel(width, height, image::Rgb([0, 128, 0]))
        .save(path)
        .unwrap();
}

fn picture(host: &Host, loco: usize) -> Option<&str> {
    host.session().locos()[loco].loco.picture()
}

#[test]
fn a_picture_is_saved_and_opened_again() {
    let (mut host, _, _, library) = host();
    host.apply(Command::AddLoco).unwrap();
    let source = library.path().join("lok.jpg");
    image_file(&source, 880, 680);
    let crop = Some(picture::Crop {
        x: 0,
        y: 0,
        width: 440,
    });
    host.apply(Command::SetPicture {
        loco: 1,
        path: source,
        crop,
    })
    .unwrap();
    let name = picture(&host, 0).unwrap().to_string();
    assert!(picture::path(library.path(), &name).exists());
    new_configuration(&mut host, "Keller").unwrap();
    open(&mut host, DEFAULT_NAME).unwrap();
    assert_eq!(picture(&host, 0), Some(name.as_str()));
}

#[test]
fn a_failed_picture_changes_nothing() {
    let (mut host, _, _, library) = host();
    host.apply(Command::AddLoco).unwrap();
    let source = library.path().join("lok.png");
    image_file(&source, 22, 17);
    let unknown = Command::SetPicture {
        loco: 9,
        path: source.clone(),
        crop: None,
    };
    assert_eq!(host.apply(unknown), Err(CommandError::UnknownLoco(9)));
    let crop = Some(picture::Crop {
        x: 1,
        y: 0,
        width: 22,
    });
    let outside = Command::SetPicture {
        loco: 1,
        path: source,
        crop,
    };
    let error = Err(CommandError::Picture(
        picture::PictureError::CropOutsideImage,
    ));
    assert_eq!(host.apply(outside), error);
    assert_eq!(picture(&host, 0), None);
    assert!(!library.path().join(media::PICTURES).exists());
}

#[test]
fn imported_pictures_are_cropped_in_the_middle() {
    let (mut host, _, _, library) = host();
    let folder = library.path().join("alt");
    fs::create_dir_all(folder.join("image")).unwrap();
    image_file(&folder.join("image/v60.png"), 1000, 340);
    let path = folder.join("anlage.json");
    // "settings" has BR 216 and V 60; only the picture of V 60 exists.
    let mut json: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(corpus("settings")).unwrap()).unwrap();
    json["locos"][0]["img_path"] = "image/fehlt.png".into();
    json["locos"][1]["img_path"] = "image/v60.png".into();
    fs::write(&path, json.to_string()).unwrap();
    host.apply(Command::ImportElectrip1 { path }).unwrap();
    assert_eq!(picture(&host, 0), None);
    let name = picture(&host, 1).unwrap();
    let saved = image::open(picture::path(library.path(), name)).unwrap();
    assert_eq!(
        (saved.width(), saved.height()),
        (picture::WIDTH, picture::HEIGHT)
    );
    let report = serde_json::to_value(host.session()).unwrap()["import_report"].clone();
    // The first three lines are the buttons of Q-015.
    assert_eq!(report.as_array().unwrap().len(), 4);
    let line = report[3].as_str().unwrap();
    assert!(
        line.starts_with("BR 216: cannot read the picture"),
        "{line}"
    );
}

#[test]
fn imported_locos_use_the_actions_of_the_configuration() {
    let (mut host, _, _, library) = host();
    for name in ["Horn", "Licht"] {
        host.apply(Command::AddAction { name: name.into() })
            .unwrap();
    }
    host.apply(Command::AddLoco).unwrap();
    for action in [2, 1] {
        let function = Function {
            action,
            number: action as u8,
            name: String::new(),
            mode: Default::default(),
            default_on: false,
            on: false,
        };
        host.apply(Command::AddFunction { loco: 1, function })
            .unwrap();
    }
    host.apply(Command::TriggerAction {
        loco: 1,
        action: 1,
        pressed: true,
    })
    .unwrap();
    let path = library.path().join("lok.zip");
    let export = Command::ExportLoco {
        loco: 1,
        path: path.clone(),
    };
    host.apply(export).unwrap();

    new_configuration(&mut host, "Keller").unwrap();
    host.apply(Command::AddAction {
        name: "Licht".into(),
    })
    .unwrap();
    host.apply(Command::ImportLoco { path }).unwrap();
    let actions = host.session().actions();
    let names: Vec<_> = actions.iter().map(|a| (a.id, a.name.as_str())).collect();
    assert_eq!(names, [(1, "Licht"), (2, "Horn")]);
    let functions = host.session().locos()[0].loco.functions();
    let used: Vec<_> = functions
        .iter()
        .map(|f| (f.action, f.number, f.on))
        .collect();
    assert_eq!(used, [(1, 2, false), (2, 1, false)]);
    open(&mut host, "Keller").unwrap();
    assert_eq!(host.session().locos().len(), 1);
}

#[test]
fn a_failed_loco_import_changes_nothing() {
    let (mut host, _, _, library) = host();
    let before = host.session().clone();
    let path = library.path().join("fehlt.zip");
    let error = host.apply(Command::ImportLoco { path }).unwrap_err();
    assert!(matches!(error, CommandError::Import(_)), "{error}");
    assert_eq!(*host.session(), before);
}

#[test]
fn a_merged_configuration_is_taken_over_while_the_locos_drive() {
    let (mut host, _, _, library) = host();
    host.apply(Command::AddLoco).unwrap();
    host.apply(Command::AddLoco).unwrap();
    host.apply(Command::SetAxis {
        loco: 1,
        deflection: 1.0,
    })
    .unwrap();
    host.poll(1.0);
    let speed = host.session().locos()[0].motion.speed();
    assert!(speed > 0.0);

    let path = config::path(library.path(), DEFAULT_NAME);
    let mut config = config::read(&path).unwrap();
    config.locos[1].set_name("Merged".into());
    config.locos.push(config.locos[1].clone());
    config::write(&path, &config).unwrap();
    host.reload().unwrap();

    assert_eq!(loco_names(&host), ["Unbenannte Lok", "Merged", "Merged"]);
    let ids: Vec<_> = host.session().locos().iter().map(|e| e.id).collect();
    assert_eq!(ids, [1, 2, 3]);
    assert_eq!(host.session().locos()[0].motion.speed(), speed);
    assert_eq!(host.session().config(), config);
}

#[test]
fn a_sound_goes_to_the_library_and_plays_from_there() {
    let library = TempDir::new().unwrap();
    let path = media::add_sound(library.path(), b"tuut", Path::new("horn.ogg")).unwrap();
    let file = library.path().join(&path);
    let audio = LogSink::new(&[(file.to_str().unwrap(), 1.0)]);
    let played = Arc::clone(&audio.played);
    let connect: Connector = Box::new(|_| Err(StationError("offline".into())));
    let mut host = Host::new(connect, Box::new(audio), library.path().into()).unwrap();
    host.apply(Command::AddLoco).unwrap();
    host.apply(Command::AddAction {
        name: "Hupe".into(),
    })
    .unwrap();
    let source = TempDir::new().unwrap();
    fs::write(source.path().join("horn.ogg"), "tuut").unwrap();
    let missing = source.path().join("missing.ogg");
    for sound in [source.path().join("horn.ogg"), missing.clone()] {
        let function = SoundFunction {
            action: 1,
            path: Some(sound),
            ..SoundFunction::default()
        };
        host.apply(Command::AddSoundFunction { loco: 1, function })
            .unwrap();
    }

    let functions = host.session().locos()[0].loco.sound_functions();
    assert_eq!(functions[0].path.as_ref(), Some(&path));
    assert_eq!(functions[1].path.as_ref(), Some(&missing));
    host.apply(Command::TriggerAction {
        loco: 1,
        action: 1,
        pressed: true,
    })
    .unwrap();
    let played = played.lock().unwrap().join("\n");
    assert!(played.contains(file.to_str().unwrap()), "{played}");
}
