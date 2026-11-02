//! B-05: acceleration and braking duration, volume and picture of a loco
//! are set through the control channel, and every client sees them.

// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

mod common;

use common::App;
use serde_json::json;
use tempfile::TempDir;

#[test]
fn durations_and_volume_are_set() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    let loco = &client.state["locos"][0];
    assert_eq!(loco["accel_duration"], 11.5);
    assert_eq!(loco["brake_duration"], 8.5);
    assert_eq!(loco["volume"], 0.8);

    for command in [
        json!({"command": "set_accel_duration", "loco": 1, "seconds": 20}),
        json!({"command": "set_brake_duration", "loco": 1, "seconds": 4.5}),
        json!({"command": "set_volume", "loco": 1, "volume": 0.25}),
    ] {
        client.command(command).unwrap();
    }
    let loco = &client.state["locos"][0];
    assert_eq!(loco["accel_duration"], 20.0);
    assert_eq!(loco["brake_duration"], 4.5);
    assert_eq!(loco["volume"], 0.25);

    // Every client sees the result.
    assert_eq!(app.connect().state, client.state);
}

#[test]
fn a_crop_of_an_image_becomes_the_picture() {
    let library = TempDir::new().unwrap();
    let app = App::start_in(library.path(), &[]);
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    assert_eq!(client.state["locos"][0]["picture"], json!(null));
    let source = library.path().join("lok.png");
    image::RgbImage::new(1100, 850).save(&source).unwrap();

    let crop = json!({"x": 100, "y": 50, "width": 220});
    client
        .command(json!({"command": "set_picture", "loco": 1, "path": source, "crop": crop}))
        .unwrap();
    let name = client.state["locos"][0]["picture"].as_str().unwrap();
    let saved = image::open(library.path().join(format!("media/{name}.png"))).unwrap();
    assert_eq!((saved.width(), saved.height()), (440, 340));
    assert_eq!(app.connect().state, client.state);

    let crop = json!({"x": 1000, "y": 0, "width": 220});
    let error = client
        .command(json!({"command": "set_picture", "loco": 1, "path": source, "crop": crop}))
        .unwrap_err();
    assert_eq!(error, "the crop must lie inside the picture");
}

#[test]
fn values_out_of_range_name_the_reason() {
    let app = App::start();
    let mut client = app.connect();
    client.command(json!({"command": "add_loco"})).unwrap();
    let before = client.state.clone();

    let brake = json!({"command": "set_brake_duration", "loco": 1, "seconds": 0});
    assert_eq!(
        client.command(brake),
        Err("the duration must be between 1 and 9999 s".into())
    );
    let volume = json!({"command": "set_volume", "loco": 1, "volume": 2});
    assert_eq!(
        client.command(volume),
        Err("the volume must be between 0 and 1".into())
    );
    assert_eq!(app.connect().state, before);
}
