use super::*;
use electrip_core::electrip1;
use std::path::Path;

/// The configuration with the most locos in the corpus.
pub(crate) fn config() -> Config {
    let path =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/corpus/configs/packages.json");
    Config {
        id: "0123456789abcdef".into(),
        ..electrip1::read(&path).unwrap().into()
    }
}

/// Two copies of the same document, as on two instances.
fn two_copies(config: &Config) -> (Document, Document) {
    let mut a = Document::new(config).unwrap();
    let b = Document::load(&a.save()).unwrap();
    (a, b)
}

fn merge_both(a: &mut Document, b: &mut Document) {
    a.merge(b).unwrap();
    b.merge(a).unwrap();
}

#[test]
fn a_configuration_comes_back_unchanged() {
    let config = config();
    assert!(config.locos.len() >= 3);
    let mut document = Document::new(&config).unwrap();
    assert_eq!(document.config().unwrap(), config);
    assert_eq!(
        Document::load(&document.save()).unwrap().config().unwrap(),
        config
    );
}

#[test]
fn an_unchanged_configuration_records_no_change() {
    let config = config();
    let mut document = Document::new(&config).unwrap();
    let heads = document.heads();
    document.update(&config).unwrap();
    assert_eq!(document.heads(), heads);
}

#[test]
fn changes_made_apart_are_merged() {
    let config = config();
    let (mut a, mut b) = two_copies(&config);
    let mut on_a = config.clone();
    on_a.locos[0].set_name("A".into());
    on_a.locos.push(config.locos[2].clone());
    a.update(&on_a).unwrap();
    let mut on_b = config.clone();
    on_b.locos[1].set_volume(0.25).unwrap();
    on_b.view.only_active = !config.view.only_active;
    b.update(&on_b).unwrap();

    merge_both(&mut a, &mut b);

    let mut expected = on_a;
    expected.locos[1].set_volume(0.25).unwrap();
    expected.view.only_active = on_b.view.only_active;
    assert_eq!(a.config().unwrap(), expected);
    assert_eq!(b.config().unwrap(), expected);
}

#[test]
fn a_change_lands_on_its_loco_when_another_loco_is_removed() {
    let config = config();
    let (mut a, mut b) = two_copies(&config);
    let mut on_a = config.clone();
    on_a.locos.remove(0);
    a.update(&on_a).unwrap();
    let mut on_b = config.clone();
    on_b.locos[2].set_name("B".into());
    b.update(&on_b).unwrap();

    merge_both(&mut a, &mut b);

    let mut expected = on_b;
    expected.locos.remove(0);
    assert_eq!(a.config().unwrap(), expected);
}

#[test]
fn the_same_field_changed_apart_ends_up_equal_everywhere() {
    let config = config();
    let (mut a, mut b) = two_copies(&config);
    for (document, name) in [(&mut a, "A"), (&mut b, "B")] {
        let mut changed = config.clone();
        changed.locos[0].set_name(name.into());
        document.update(&changed).unwrap();
    }

    merge_both(&mut a, &mut b);

    let name = a.config().unwrap().locos[0].name().to_string();
    assert!(name == "A" || name == "B");
    assert_eq!(a.config().unwrap(), b.config().unwrap());
}
