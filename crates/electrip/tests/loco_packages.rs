//! B-20: a loco package of Electrip 1 is imported through the control
//! channel, exported again and imported as a copy.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::App;
use serde_json::json;
use std::path::Path;
use tempfile::TempDir;

#[test]
fn a_package_is_imported_and_exported() {
    let library = TempDir::new().unwrap();
    let app = App::start_in(library.path(), &[]);
    let mut client = app.connect();
    let package =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/corpus/packages/BR 216.zip");
    client
        .command(json!({"command": "import_loco", "path": package}))
        .unwrap();
    let loco = client.state["locos"][0].clone();
    assert_eq!(loco["name"], "BR 216");
    assert_eq!(loco["decoder"]["address"], 2);
    let picture = loco["picture"].as_str().unwrap();
    assert!(library.path().join(format!("media/{picture}.png")).exists());
    assert_eq!(client.state["import_report"], json!([]));

    let path = library.path().join("export.zip");
    client
        .command(json!({"command": "export_loco", "loco": 1, "path": path}))
        .unwrap();
    client
        .command(json!({"command": "import_loco", "path": path}))
        .unwrap();
    let mut copy = client.state["locos"][1].clone();
    assert_eq!(copy["id"], 2);
    copy["id"] = 1.into();
    assert_eq!(copy, loco);
    assert_eq!(app.connect().state, client.state);

    let missing = library.path().join("fehlt.zip");
    let error = client
        .command(json!({"command": "import_loco", "path": missing}))
        .unwrap_err();
    assert!(error.starts_with("cannot read the file: "), "{error}");
}
