use super::*;
use electrip_core::station::StationError;
use tempfile::TempDir;

/// A host and its library, deleted when dropped.
fn host() -> (Host, TempDir) {
    let library = TempDir::new().unwrap();
    let connect = Box::new(|_: &_| Err(StationError("no station".into())));
    let host = Host::new(connect, library.path().into()).unwrap();
    (host, library)
}

#[test]
fn execute_applies_a_command() {
    let (mut host, _library) = host();
    assert_eq!(execute(&mut host, r#"{"command": "add_loco"}"#), Ok(()));
    assert_eq!(host.session().locos().len(), 1);
}

#[test]
fn execute_explains_invalid_json() {
    let (mut host, _library) = host();
    let error = execute(&mut host, r#"{"command": "fly"}"#).unwrap_err();
    assert!(
        error.starts_with("invalid command: unknown variant `fly`"),
        "{error}"
    );
}

#[test]
fn execute_explains_a_failed_command() {
    let (mut host, _library) = host();
    let error = execute(
        &mut host,
        r#"{"command": "set_address", "loco": 1, "address": 3}"#,
    );
    assert_eq!(error, Err("there is no loco with id 1".into()));
}

#[test]
fn replies_report_success_or_the_error() {
    assert_eq!(reply(&Ok(())), json!({"type": "reply", "ok": true}));
    assert_eq!(
        reply(&Err("oops".into())),
        json!({"type": "reply", "ok": false, "error": "oops"})
    );
}
