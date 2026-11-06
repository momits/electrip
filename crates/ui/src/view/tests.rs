#![allow(clippy::unwrap_used)]

use super::*;
use electrip_core::session::Command;
use image::{Rgb, RgbImage};
use serde_json::{Value, json};
use slint::ComponentHandle;
use slint::Rgb8Pixel;
use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Platform, WindowAdapter};
use std::io::{BufRead, BufReader};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::rc::Rc;

fn loco(id: i32, name: &str) -> Value {
    json!({
        "id": id, "name": name, "max_speed": 100.0, "speed": 0.0, "forward": true,
        "picture": null, "sound_model": null, "sound": "off",
        "sound_functions": [], "event_sounds": [], "functions": []
    })
}

fn state(locos: Vec<Value>, devices: Value) -> State {
    let station = json!({"connected": true, "track_power": false});
    let state = json!({"locos": locos, "devices": devices, "station": station});
    serde_json::from_value(state).unwrap()
}

/// A loco with one button of each group, each defined in reverse order.
fn loco_with_buttons() -> Value {
    let mut loco = loco(1, "V 60");
    loco["sound_model"] = json!({"engine": {"type": "diesel"}});
    loco["sound"] = json!("starting");
    loco["functions"] = json!([
        {"action": 1, "number": 0, "name": "Licht", "on": true},
        {"action": 2, "number": 2, "name": "", "on": false}
    ]);
    loco["event_sounds"] = json!([{"action": 3, "name": "Pfiff", "active": true}]);
    loco["sound_functions"] = json!([{"action": 4, "name": "Glocke", "on": false}]);
    loco
}

#[test]
fn buttons_in_the_order_of_electrip_1() {
    let state = state(vec![loco_with_buttons()], json!([]));
    let controllers = controllers(&state, Path::new(""));
    let buttons: Vec<_> = controllers[0]
        .buttons
        .iter()
        .map(|b| (b.kind, b.label.to_string(), b.on, b.action))
        .collect();
    assert_eq!(
        buttons,
        [
            (ButtonKind::DrivingSound, String::new(), true, 0),
            (ButtonKind::SoundFunction, "Glocke".into(), false, 4),
            (ButtonKind::EventSound, "Pfiff".into(), true, 3),
            (ButtonKind::Function, "Licht".into(), true, 1),
            (ButtonKind::Function, "F2".into(), false, 2),
        ]
    );
}

#[test]
fn without_sound_model_no_driving_sound_button() {
    let state = state(vec![loco(1, "Köf")], json!([]));
    assert_eq!(controllers(&state, Path::new(""))[0].buttons.row_count(), 0);
}

#[test]
fn devices_mark_their_locos() {
    let devices =
        json!([{"loco": 2, "color": 3}, {"loco": null, "color": 1}, {"loco": 2, "color": 5}]);
    let state = state(vec![loco(1, "A"), loco(2, "B")], devices);
    let controllers = controllers(&state, Path::new(""));
    assert_eq!(controllers[0].devices.row_count(), 0);
    assert_eq!(controllers[1].devices.iter().collect::<Vec<_>>(), [3, 5]);
}

#[test]
fn missing_picture_shows_none() {
    let mut loco = loco(1, "A");
    loco["picture"] = json!("missing.png");
    let state = state(vec![loco], json!([]));
    assert_eq!(
        controllers(&state, Path::new(""))[0].picture.size().width,
        0
    );
}

#[test]
fn driving_and_switching_keep_the_buttons() {
    let model = ModelRc::new(VecModel::<Controller>::default());
    let mut loco = loco_with_buttons();
    let show = |loco: &Value| {
        let rows = controllers(&state(vec![loco.clone()], json!([])), Path::new(""));
        update_controllers(&model, rows);
        model.row_data(0).unwrap()
    };
    let before = show(&loco);
    loco["speed"] = json!(20.0);
    loco["functions"][1]["on"] = json!(true);
    let after = show(&loco);
    assert_eq!(after.speed, 20.0);
    assert!(after.buttons.row_data(4).unwrap().on);
    // The same model, so the window keeps the button elements and a held
    // button gets its release.
    assert!(before.buttons == after.buttons);
}

/// Renders the window without a display.
struct Headless(Rc<MinimalSoftwareWindow>);

impl Platform for Headless {
    fn create_window_adapter(&self) -> Result<Rc<dyn WindowAdapter>, slint::PlatformError> {
        Ok(self.0.clone())
    }
}

const WIDTH: u32 = 800;
const HEIGHT: u32 = 600;

fn screenshot(window: &MinimalSoftwareWindow) -> RgbImage {
    let mut pixels = vec![Rgb8Pixel::default(); (WIDTH * HEIGHT) as usize];
    window.draw_if_needed(|renderer| {
        renderer.render(&mut pixels, WIDTH as usize);
    });
    let bytes = pixels.iter().flat_map(|p| [p.r, p.g, p.b]).collect();
    RgbImage::from_raw(WIDTH, HEIGHT, bytes).unwrap()
}

/// Saved for the agent and Mo to look at.
fn save(image: &RgbImage, name: &str) {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../target/test-logs/screenshots");
    std::fs::create_dir_all(&dir).unwrap();
    image.save(dir.join(name)).unwrap();
}

/// Slint has one platform per process, so one test covers the window: it
/// shows the state and sends commands the host understands.
#[test]
fn window_shows_the_state_and_sends_commands() {
    let window = MinimalSoftwareWindow::new(RepaintBufferType::NewBuffer);
    slint::platform::set_platform(Box::new(Headless(window.clone()))).unwrap();
    window.set_size(slint::PhysicalSize::new(WIDTH, HEIGHT));
    let media = tempfile::tempdir().unwrap();
    RgbImage::from_fn(440, 340, |x, y| Rgb([(x / 2) as u8, (y / 2) as u8, 120]))
        .save(media.path().join("picture.png"))
        .unwrap();
    let mut driven = loco_with_buttons();
    driven["speed"] = json!(60.0);
    driven["picture"] = json!("picture.png");
    let state = state(
        vec![driven, loco(2, "Köf II")],
        json!([{"loco": 1, "color": 1}]),
    );

    let main = MainWindow::new().unwrap();
    main.set_controllers(ModelRc::new(VecModel::<Controller>::default()));
    show(&main, &state, media.path());
    main.show().unwrap();
    let image = screenshot(&window);
    save(&image, "control_view.png");

    // The controlled loco has the color of its device, the other none.
    assert_eq!(*image.get_pixel(10, 200), Rgb([0x6a, 0xa9, 0xd0]));
    assert_eq!(*image.get_pixel(146, 200), Rgb([0xfa, 0xfa, 0xfa]));
    // The emergency stop is red while the track power is off.
    assert_eq!(*image.get_pixel(5, HEIGHT - 5), Rgb([0xcd, 0x44, 0x44]));

    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let client = TcpStream::connect(listener.local_addr().unwrap()).unwrap();
    crate::connect_callbacks(&main, Rc::new(client));
    main.invoke_reverse(1);
    main.invoke_toggle_sound(1);
    main.invoke_trigger(1, 4, true);
    main.invoke_toggle_power();
    let (host, _) = listener.accept().unwrap();
    let commands: Vec<Command> = BufReader::new(host)
        .lines()
        .take(4)
        .map(|l| serde_json::from_str(&l.unwrap()).unwrap())
        .collect();
    assert_eq!(
        commands,
        [
            Command::Reverse { loco: 1 },
            Command::ToggleSound { loco: 1 },
            Command::TriggerAction {
                loco: 1,
                action: 4,
                pressed: true
            },
            Command::TogglePower,
        ]
    );
}
