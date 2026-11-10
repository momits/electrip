use super::*;
use crate::tests::{request, serve_library};
use electrip_core::config;
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
    let (a, library_a) = serve_library(TempDir::new().unwrap());
    let copy = TempDir::new().unwrap();
    let file = config::path(library_a.path(), config::DEFAULT_NAME);
    fs::copy(&file, config::path(copy.path(), config::DEFAULT_NAME)).unwrap();
    let (b, _library_b) = serve_library(copy);
    // The documents get a common history, so they merge field by field.
    sync(a, b).unwrap();
    request(a, json!({"command": "add_loco"}));
    request(b, json!({"command": "add_action", "name": "Licht"}));

    sync(a, b).unwrap();

    for host in [a, b] {
        let state = state(host);
        assert_eq!(state["locos"].as_array().unwrap().len(), 1, "{host}");
        assert_eq!(state["actions"][0]["name"], "Licht", "{host}");
    }
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
