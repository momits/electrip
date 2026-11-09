#![allow(clippy::unwrap_used)]

use super::*;
use crate::generated::DeviceColors;
use electrip_core::config::View;
use electrip_core::picture::Crop;
use electrip_core::session::Command;
use image::{Rgb, RgbImage};
use serde_json::{Value, json};
use slint::ComponentHandle;
use slint::Rgb8Pixel;
use slint::platform::software_renderer::{MinimalSoftwareWindow, RepaintBufferType};
use slint::platform::{Key, Platform, PointerEventButton, WindowAdapter, WindowEvent};
use std::io::{BufRead, BufReader};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::rc::Rc;

fn loco(id: i32, name: &str) -> Value {
    json!({
        "id": id, "name": name, "max_speed": 100.0, "volume": 0.8, "speed": 0.0, "forward": true,
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

fn device(loco: impl Into<Option<i32>>, number: i32) -> Value {
    json!({"loco": loco.into(), "number": number, "focus": false})
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
/// device number 1 on loco 1.
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

/// The colors of the input devices from the palette of the window.
fn device_colors(main: &MainWindow) -> Vec<[u8; 3]> {
    let palette = main.global::<DeviceColors>().get_palette();
    palette
        .iter()
        .map(|c| [c.red(), c.green(), c.blue()])
        .collect()
}

/// The contrast of white text on `color` after WCAG 2.
fn contrast_to_white(color: [u8; 3]) -> f64 {
    let linear = |c: u8| {
        let c = f64::from(c) / 255.0;
        if c <= 0.04045 {
            c / 12.92
        } else {
            ((c + 0.055) / 1.055).powf(2.4)
        }
    };
    let [r, g, b] = color.map(linear);
    1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05)
}

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

/// An image of `width`×`height` whose red is the column, green the row.
fn gradient(width: u32, height: u32) -> RgbImage {
    RgbImage::from_fn(width, height, |x, y| Rgb(gradient_at(x as f32, y as f32)))
}

/// The top left corner of the picture in the dialog.
const FRAME: (u32, u32) = (180, 114);

fn gradient_at(x: f32, y: f32) -> [u8; 3] {
    [(x / 4.0) as u8, (y / 2.0) as u8, 0]
}

fn assert_near(pixel: &Rgb<u8>, expected: [u8; 3]) {
    let near = pixel
        .0
        .iter()
        .zip(expected)
        .all(|(a, b)| a.abs_diff(b) <= 3);
    assert!(near, "{pixel:?} is not near {expected:?}");
}

fn press(window: &MinimalSoftwareWindow, x: u32, y: u32) {
    let position = slint::LogicalPosition::new(x as f32, y as f32);
    let button = PointerEventButton::Left;
    window.dispatch_event(WindowEvent::PointerPressed { position, button });
}

fn release(window: &MinimalSoftwareWindow, x: u32, y: u32) {
    let position = slint::LogicalPosition::new(x as f32, y as f32);
    let button = PointerEventButton::Left;
    window.dispatch_event(WindowEvent::PointerReleased { position, button });
}

fn click(window: &MinimalSoftwareWindow, x: u32, y: u32) {
    press(window, x, y);
    release(window, x, y);
}

fn drag(window: &MinimalSoftwareWindow, from: (u32, u32), to: (u32, u32)) {
    press(window, from.0, from.1);
    let position = slint::LogicalPosition::new(to.0 as f32, to.1 as f32);
    window.dispatch_event(WindowEvent::PointerMoved { position });
    release(window, to.0, to.1);
}

fn type_text(window: &MinimalSoftwareWindow, text: &str) {
    for c in text.chars() {
        let text = SharedString::from(c.to_string());
        window.dispatch_event(WindowEvent::KeyPressed { text: text.clone() });
        window.dispatch_event(WindowEvent::KeyReleased { text });
    }
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
    driven["picture"] = json!("picture");
    let state = state(vec![driven, loco(2, "Köf II")], json!([device(1, 1)]));

    let main = MainWindow::new().unwrap();
    main.set_controllers(ModelRc::new(VecModel::<Controller>::default()));
    main.show().unwrap();
    let colors = device_colors(&main);
    show(&main, &state, media.path());
    let image = screenshot(&window);
    save(&image, "control_view.png");

    // The controlled loco has the color of its device, the other none.
    assert_eq!(*image.get_pixel(10, 200), Rgb(colors[0]));
    assert_eq!(*image.get_pixel(146, 200), Rgb([0xfa, 0xfa, 0xfa]));
    // The picture from the media directory, its blue is the same
    // everywhere; where exactly depends on the font of the name.
    assert_eq!(image.get_pixel(67, 102).0[2], 120);
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
    assert_eq!(*image.get_pixel(WIDTH - 30, 200), Rgb(colors[0]));
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

    // B-03: thirty devices, each on its own loco, in a wide window; the
    // eight colors repeat, white numbers stay readable on each.
    assert_eq!(colors.len(), 8);
    for color in &colors {
        assert!(contrast_to_white(*color) >= 3.0, "{color:?}");
    }
    window.set_size(slint::PhysicalSize::new(2780, HEIGHT));
    let locos = (1..=30).map(|id| loco(id, &format!("Lok {id}"))).collect();
    let devices = (1..=30).map(|id| device(id, id)).collect();
    show(&main, &self::state(locos, devices), media.path());
    let image = screenshot(&window);
    save(&image, "control_view_devices.png");
    for i in 0..30 {
        let color = colors[i % 8];
        let left = 6 + 92 * i as u32;
        // The loco has the color of its device, and the symbol above the
        // name is a white circle with the number in that color.
        assert_eq!(*image.get_pixel(left + 10, 200), Rgb(color));
        // The fonts differ by system, so the darkest pixel of the number
        // only has to be nearest to that color.
        let symbol = |x, y| image.get_pixel(left + x, y).0;
        assert_eq!(symbol(43, 14), [0xff; 3]);
        let pixels = (36..50).flat_map(|x| (16..30).map(move |y| (x, y)));
        let darkest = pixels
            .map(|(x, y)| symbol(x, y))
            .min_by_key(|p| p.map(u32::from).iter().sum::<u32>());
        let distance = |c: &[u8; 3]| {
            (0..3)
                .map(|k| darkest.unwrap()[k].abs_diff(c[k]) as u32)
                .sum::<u32>()
        };
        assert_eq!(
            colors.iter().min_by_key(|c| distance(c)),
            Some(&color),
            "device {}",
            i + 1
        );
    }

    // Nine devices on one loco: the symbols wrap into rows of five.
    window.set_size(slint::PhysicalSize::new(WIDTH, HEIGHT));
    let devices = (1..=9).map(|id| device(1, id)).collect();
    show(
        &main,
        &self::state(vec![loco(1, "Lok 1")], devices),
        media.path(),
    );
    let image = screenshot(&window);
    save(&image, "control_view_wrapped.png");
    let rows: Vec<_> = (0..3)
        .map(|row| *image.get_pixel(16, 17 + 24 * row))
        .collect();
    assert_eq!(rows, [Rgb([0xff; 3]), Rgb([0xff; 3]), Rgb(colors[0])]);

    // B-25: the texts follow the language, German or English.
    let bottom_bar = |language, name| {
        slint::select_bundled_translation(language).unwrap();
        window.request_redraw();
        let image = screenshot(&window);
        save(&image, name);
        image::imageops::crop_imm(&image, 0, HEIGHT - 40, WIDTH, 40).to_image()
    };
    let german = bottom_bar("de", "control_view_de.png");
    let english = bottom_bar("en", "control_view_en.png");
    assert_ne!(german, english);

    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let client = TcpStream::connect(listener.local_addr().unwrap()).unwrap();
    crate::connect_callbacks(&main, Rc::new(client));
    main.invoke_reverse(1);
    main.invoke_toggle_sound(1);
    main.invoke_trigger(1, 4, true);
    main.invoke_toggle_power();
    main.invoke_set_view(false, true);

    // B-05: click the picture, load an image, drag and zoom the crop.
    window.set_size(slint::PhysicalSize::new(WIDTH, HEIGHT));
    show(&main, &state, media.path());
    let source = media.path().join("source.png");
    gradient(880, 340).save(&source).unwrap();
    click(&window, 60, 80);
    save(&screenshot(&window), "loco_dialog.png");
    click(&window, 300, 90);
    type_text(&window, source.to_str().unwrap());
    click(&window, 580, 90);
    // The largest crop in the middle at first, then dragged 100 px to the
    // right, so it shows 100 px more on the left.
    drag(&window, (400, 284), (500, 284));
    let image = screenshot(&window);
    save(&image, "loco_dialog_dragged.png");
    assert_near(image.get_pixel(FRAME.0, FRAME.1), gradient_at(120.0, 0.0));
    // Zoomed in 4 times around the middle of the crop.
    click(&window, 600, 474);
    type_text(&window, &SharedString::from(Key::End));
    let image = screenshot(&window);
    save(&image, "loco_dialog_zoomed.png");
    assert_near(
        image.get_pixel(FRAME.0 + 2, FRAME.1 + 2),
        gradient_at(285.5, 128.0),
    );
    click(&window, 443, 506);
    click(&window, 434, 542);
    let (host, _) = listener.accept().unwrap();
    // A missed click fails instead of waiting for ever.
    host.set_read_timeout(Some(std::time::Duration::from_secs(5)))
        .unwrap();
    let commands: Vec<Command> = BufReader::new(host)
        .lines()
        .take(7)
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
            Command::SetVolume {
                loco: 1,
                volume: 0.5
            },
            Command::SetPicture {
                loco: 1,
                path: source,
                crop: Some(Crop {
                    x: 285,
                    y: 127,
                    width: 110
                })
            },
        ]
    );
}
