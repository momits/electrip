use super::*;
use crate::function::Function;
use crate::host::Connector;
use crate::host::tests::{host, set_server};
use crate::session::Command;
use crate::station::StationError;

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
    let reopened = Host::new(connect, library.path().into()).unwrap();
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
    new_configuration(&mut host, "Keller").unwrap();
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
    rename(&mut host, "Dachboden").unwrap();
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
    assert_eq!(host.session().config(), Config::default());
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
    let saved = config::read(&host.path("settings").unwrap()).unwrap();
    assert_eq!(saved, host.session().config());
    let exists = Err(CommandError::ConfigurationExists("settings".into()));
    assert_eq!(host.apply(Command::ImportElectrip1 { path }), exists);
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
