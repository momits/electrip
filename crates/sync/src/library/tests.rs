use super::*;
use crate::tests::config;
use tempfile::TempDir;

const NAME: &str = "Keller";

/// A library with the configuration of the corpus, as on one instance.
fn library(config: &Config) -> TempDir {
    let dir = TempDir::new().unwrap();
    config::write(&config::path(dir.path(), NAME), config).unwrap();
    dir
}

fn read(library: &TempDir) -> Config {
    config::read(&config::path(library.path(), NAME)).unwrap()
}

fn change(library: &TempDir, change: impl FnOnce(&mut Config)) {
    let mut config = read(library);
    change(&mut config);
    config::write(&config::path(library.path(), NAME), &config).unwrap();
}

#[test]
fn the_document_is_kept_under_the_configuration_id() {
    let config = config();
    let a = library(&config);
    document(a.path(), NAME).unwrap();
    let path = a.path().join(format!("sync/{}.automerge", config.id));
    let bytes = fs::read(path).unwrap();
    assert_eq!(Document::load(&bytes).unwrap().config().unwrap(), config);
}

#[test]
fn changes_of_two_libraries_end_up_in_both_files() {
    let config = config();
    let (a, b) = (library(&config), library(&config));
    assert!(!merge(b.path(), NAME, &mut document(a.path(), NAME).unwrap()).unwrap());
    change(&a, |config| config.locos[0].set_name("A".into()));
    change(&b, |config| config.locos[1].set_name("B".into()));

    assert!(merge(b.path(), NAME, &mut document(a.path(), NAME).unwrap()).unwrap());
    assert!(merge(a.path(), NAME, &mut document(b.path(), NAME).unwrap()).unwrap());

    let mut expected = config;
    expected.locos[0].set_name("A".into());
    expected.locos[1].set_name("B".into());
    assert_eq!(read(&a), expected);
    assert_eq!(read(&b), expected);
}

#[test]
fn an_id_cannot_reach_a_file_outside_the_library() {
    let a = library(&Config {
        id: "../outside".into(),
        ..config()
    });
    let result = document(a.path(), NAME);
    assert!(matches!(result, Err(Error::InvalidId(id)) if id == "../outside"));
}

#[test]
fn ids_name_the_configurations() {
    let config = config();
    let a = library(&config);
    assert_eq!(ids(a.path()).unwrap(), [(config.id, NAME.to_string())]);
}

#[test]
fn a_configuration_taken_twice_merges_into_the_first_copy() {
    let config = config();
    let a = library(&config);
    let b = TempDir::new().unwrap();
    let other = Config {
        id: config::new_id(),
        ..Config::default()
    };
    config::write(&config::path(b.path(), NAME), &other).unwrap();

    let taken = take(b.path(), NAME, &mut document(a.path(), NAME).unwrap()).unwrap();
    assert_eq!(taken, format!("{NAME} 2"));
    change(&a, |config| config.locos[0].set_name("A".into()));
    let again = take(b.path(), NAME, &mut document(a.path(), NAME).unwrap()).unwrap();

    assert_eq!(again, taken);
    assert_eq!(
        config::read(&config::path(b.path(), &taken)).unwrap(),
        read(&a)
    );
    assert_eq!(read(&b), other);
}

#[test]
fn a_name_cannot_reach_a_file_outside_the_library() {
    let a = library(&config());
    let b = TempDir::new().unwrap();
    let result = take(
        b.path(),
        "../outside",
        &mut document(a.path(), NAME).unwrap(),
    );
    assert!(matches!(result, Err(Error::InvalidId(name)) if name == "../outside"));
}

#[test]
fn an_unchanged_configuration_is_not_written_again() {
    let config = config();
    let (a, b) = (library(&config), library(&config));
    merge(b.path(), NAME, &mut document(a.path(), NAME).unwrap()).unwrap();
    let path = |dir: &TempDir| dir.path().join(format!("sync/{}.automerge", config.id));
    let old = std::time::SystemTime::UNIX_EPOCH;
    for dir in [&a, &b] {
        fs::File::options()
            .write(true)
            .open(path(dir))
            .unwrap()
            .set_modified(old)
            .unwrap();
    }

    merge(b.path(), NAME, &mut document(a.path(), NAME).unwrap()).unwrap();

    for dir in [&a, &b] {
        assert_eq!(fs::metadata(path(dir)).unwrap().modified().unwrap(), old);
    }
    change(&a, |config| config.locos[0].set_name("A".into()));
    merge(b.path(), NAME, &mut document(a.path(), NAME).unwrap()).unwrap();
    for dir in [&a, &b] {
        assert_ne!(fs::metadata(path(dir)).unwrap().modified().unwrap(), old);
    }
}
