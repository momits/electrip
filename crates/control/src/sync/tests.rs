use super::*;
use crate::tests::{request, serve_library};
use electrip_core::{config, picture};
use std::fs;
use tempfile::TempDir;

/// The state the host at `host` greets with.
fn state(host: SocketAddr) -> Value {
    let stream = TcpStream::connect(host).unwrap();
    let mut lines = BufReader::new(stream).lines();
    lines.next(); // hello
    let message: Value = serde_json::from_str(&lines.next().unwrap().unwrap()).unwrap();
    message["state"].clone()
}

#[test]
fn two_hosts_merge_the_changes_of_a_shared_configuration() {
    let [(a, _library_a), (b, _library_b)] = shared_hosts();
    request(a, json!({"command": "add_loco"}));
    request(b, json!({"command": "add_action", "name": "Licht"}));

    sync(a, b).unwrap();

    for host in [a, b] {
        let state = state(host);
        assert_eq!(state["locos"].as_array().unwrap().len(), 1, "{host}");
        assert_eq!(state["actions"][0]["name"], "Licht", "{host}");
    }
}

/// Two hosts with a copy of the same configuration. The documents get a
/// common history, so they merge field by field.
fn shared_hosts() -> [(SocketAddr, TempDir); 2] {
    let (a, library) = serve_library(TempDir::new().unwrap());
    let copy = TempDir::new().unwrap();
    let file = config::path(library.path(), config::DEFAULT_NAME);
    fs::copy(&file, config::path(copy.path(), config::DEFAULT_NAME)).unwrap();
    let (b, copy) = serve_library(copy);
    sync(a, b).unwrap();
    [(a, library), (b, copy)]
}

#[test]
fn a_loco_comes_to_the_other_host_with_its_picture() {
    let [(a, library_a), (b, library_b)] = shared_hosts();
    let source = library_a.path().join("lok.png");
    image::RgbImage::new(440, 340).save(&source).unwrap();
    request(a, json!({"command": "add_loco"}));
    request(
        a,
        json!({"command": "set_picture", "loco": 1, "path": source}),
    );

    sync(a, b).unwrap();

    let name = state(b)["locos"][0]["picture"]
        .as_str()
        .unwrap()
        .to_string();
    let media = |library: &TempDir| fs::read(picture::path(&library.path().join("media"), &name));
    assert_eq!(media(&library_b).unwrap(), media(&library_a).unwrap());
}

#[test]
fn a_host_rejects_an_unknown_configuration() {
    let (a, _library) = serve_library(TempDir::new().unwrap());
    let reply = request(a, json!({"command": "sync_configuration", "id": "x"}));
    assert_eq!(reply["error"], "there is no configuration with id x");
}

#[test]
fn documents_go_as_hex() {
    assert_eq!(encode(&[0, 0xab, 7]), "00ab07");
    assert_eq!(decode("00ab07"), Some(vec![0, 0xab, 7]));
    assert_eq!(decode("0g"), None);
    assert_eq!(decode("abc"), None);
}
