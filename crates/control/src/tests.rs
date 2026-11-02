use super::*;

#[test]
fn execute_applies_a_command() {
    let mut session = Session::default();
    assert_eq!(execute(&mut session, r#"{"command": "add_loco"}"#), Ok(()));
    assert_eq!(session.locos().len(), 1);
}

#[test]
fn execute_explains_invalid_json() {
    let mut session = Session::default();
    let error = execute(&mut session, r#"{"command": "fly"}"#).unwrap_err();
    assert!(
        error.starts_with("invalid command: unknown variant `fly`"),
        "{error}"
    );
}

#[test]
fn execute_explains_a_failed_command() {
    let mut session = Session::default();
    let error = execute(
        &mut session,
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
