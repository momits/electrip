#![allow(clippy::unwrap_used)]

use super::*;
use electrip_core::config::View;
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
    let view = json!({"auto_focus": true, "only_active": false});
    let state = json!({"locos": locos, "devices": devices, "station": station, "view": view});
    serde_json::from_value(state).unwrap()
}

fn device(loco: impl Into<Option<i32>>, color: i32) -> Value {
    json!({"loco": loco.into(), "color": color, "focus": false})
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
    let devices = json!([device(2, 3), device(None, 1), device(2, 5)]);
    let state = state(vec![loco(1, "A"), loco(2, "B")], devices);
    let controllers = controllers(&state, Path::new(""));
    assert_eq!(controllers[0].devices.row_count(), 0);
    assert_eq!(controllers[1].devices.iter().collect::<Vec<_>>(), [3, 5]);
}

#[test]
fn only_active_shows_controlled_or_moving_locos() {
    let mut moving = loco(2, "B");
    moving["speed"] = json!(0.5);
    let locos = vec![loco(1, "A"), moving, loco(3, "C"), loco(4, "D")];
    let mut state = state(locos, json!([device(3, 1)]));
    state.view.only_active = true;
    let ids: Vec<_> = controllers(&state, Path::new(""))
        .iter()
        .map(|c| c.id)
        .collect();
    assert_eq!(ids, [2, 3]);
}

/// The loco to bring into view for `devices`, when the window shows the
/// device of color 1 on loco 1.
fn focus_after(devices: Value, auto_focus: bool) -> Option<i32> {
    let locos = vec![loco(1, "A"), loco(2, "B"), loco(3, "C")];
    let shown = state(locos.clone(), json!([device(1, 1)]));
    let shown = ModelRc::new(VecModel::from(controllers(&shown, Path::new(""))));
    let mut state = state(locos, devices);
    state.view.auto_focus = auto_focus;
    focus(&state, &shown)
}

#[test]
fn auto_focus_shows_the_new_loco_of_a_device() {
    assert_eq!(focus_after(json!([device(1, 1)]), true), None);
    assert_eq!(
        focus_after(json!([device(1, 1), device(3, 2)]), true),
        Some(3)
    );
    assert_eq!(focus_after(json!([device(2, 1)]), true), Some(2));
    assert_eq!(focus_after(json!([device(2, 1)]), false), None);
    assert_eq!(focus_after(json!([device(None, 2)]), true), None);
}

#[test]
fn holding_focus_shows_the_loco_of_the_device() {
    let mut held = device(3, 2);
    held["focus"] = json!(true);
    let devices = json!([device(2, 1), held]);
    assert_eq!(focus_after(devices.clone(), true), Some(3));
    assert_eq!(focus_after(devices, false), Some(3));
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
    let size = window.size();
    let mut pixels = vec![Rgb8Pixel::default(); (size.width * size.height) as usize];
    window.draw_if_needed(|renderer| {
        renderer.render(&mut pixels, size.width as usize);
    });
    let bytes = pixels.iter().flat_map(|p| [p.r, p.g, p.b]).collect();
    RgbImage::from_raw(size.width, size.height, bytes).unwrap()
}

/// Saved for the agent and Mo to look at.
fn save(image: &RgbImage, name: &str) {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../target/test-logs/screenshots");
    std::fs::create_dir_all(&dir).unwrap();
    image.save(dir.join(name)).unwrap();
}

/// Colors of the input devices 1 to 12.
const DEVICE_COLORS: [[u8; 3]; 12] = [
    [0x6a, 0xa9, 0xd0],
    [0xf3, 0x9d, 0x41],
    [0xf0, 0x80, 0x70],
    [0x4a, 0x7a, 0x99],
    [0xa8, 0xa8, 0xa8],
    [0x8d, 0xcc, 0x8d],
    [0xff, 0xc2, 0x26],
    [0xc9, 0x8a, 0xca],
    [0x4f, 0xa6, 0xb2],
    [0xa0, 0x78, 0x5a],
    [0xe0, 0x7a, 0xb0],
    [0x7a, 0x8a, 0x3a],
];

/// Colors of switched-off buttons: driving sound, sound functions, event
/// sounds, functions.
const BUTTON_COLORS: [[u8; 3]; 4] = [
    [0xff, 0xb0, 0x48],
    [0xb4, 0xb4, 0xfa],
    [0xff, 0x9a, 0x82],
    [0xec; 3],
];

/// The button colors from top to bottom in column `x`.
fn button_colors(image: &RgbImage, x: u32) -> Vec<Rgb<u8>> {
    let mut column: Vec<_> = (0..HEIGHT).map(|y| *image.get_pixel(x, y)).collect();
    column.dedup();
    column.retain(|p| BUTTON_COLORS.contains(&p.0));
    column
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
    let state = state(vec![driven, loco(2, "Köf II")], json!([device(1, 1)]));

    let main = MainWindow::new().unwrap();
    main.set_controllers(ModelRc::new(VecModel::<Controller>::default()));
    main.show().unwrap();
    show(&main, &state, media.path());
    let image = screenshot(&window);
    save(&image, "control_view.png");

    // The controlled loco has the color of its device, the other none.
    assert_eq!(*image.get_pixel(10, 200), Rgb(DEVICE_COLORS[0]));
    assert_eq!(*image.get_pixel(146, 200), Rgb([0xfa, 0xfa, 0xfa]));
    // The emergency stop is red while the track power is off.
    assert_eq!(*image.get_pixel(5, HEIGHT - 5), Rgb([0xcd, 0x44, 0x44]));

    // Twelve locos: compact controllers, and auto-focus scrolls to the
    // last one, which the device changed to.
    let locos = (1..=12).map(|id| loco(id, &format!("Lok {id}"))).collect();
    show(
        &main,
        &self::state(locos, json!([device(12, 1)])),
        media.path(),
    );
    let image = screenshot(&window);
    save(&image, "control_view_compact.png");
    assert_eq!(*image.get_pixel(WIDTH - 30, 200), Rgb(DEVICE_COLORS[0]));
    assert_eq!(*image.get_pixel(WIDTH - 100, 200), Rgb([0xfa, 0xfa, 0xfa]));

    // B-19: driving sound, sound functions, event sounds, functions, each
    // group in its own color.
    let mut off = loco_with_buttons();
    off["sound"] = json!("off");
    off["functions"][0]["on"] = json!(false);
    off["event_sounds"][0]["active"] = json!(false);
    show(&main, &self::state(vec![off], json!([])), media.path());
    let image = screenshot(&window);
    save(&image, "control_view_buttons.png");
    let [driving, sound, event, function] = BUTTON_COLORS.map(Rgb);
    assert_eq!(
        button_colors(&image, 20),
        [driving, sound, event, function, function]
    );

    // B-03: twelve devices, each on its own loco, in a wide window.
    window.set_size(slint::PhysicalSize::new(1300, HEIGHT));
    let locos = (1..=12).map(|id| loco(id, &format!("Lok {id}"))).collect();
    let devices = (1..=12).map(|id| device(id, id)).collect();
    show(&main, &self::state(locos, devices), media.path());
    let image = screenshot(&window);
    save(&image, "control_view_devices.png");
    for (i, color) in DEVICE_COLORS.into_iter().enumerate() {
        let left = 6 + 92 * i as u32;
        // The loco has the color of its device, and the symbol above the
        // name is a white circle with the number in that color.
        assert_eq!(*image.get_pixel(left + 10, 200), Rgb(color));
        let symbol = |x, y| image.get_pixel(left + x, y).0;
        assert_eq!(symbol(43, 15), [0xff; 3]);
        assert!((36..50).any(|x| (16..28).any(|y| symbol(x, y) == color)));
    }

    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let client = TcpStream::connect(listener.local_addr().unwrap()).unwrap();
    crate::connect_callbacks(&main, Rc::new(client));
    main.invoke_reverse(1);
    main.invoke_toggle_sound(1);
    main.invoke_trigger(1, 4, true);
    main.invoke_toggle_power();
    main.invoke_set_view(false, true);
    let (host, _) = listener.accept().unwrap();
    let commands: Vec<Command> = BufReader::new(host)
        .lines()
        .take(5)
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
            Command::SetView {
                view: View {
                    auto_focus: false,
                    only_active: true
                }
            },
        ]
    );
}
