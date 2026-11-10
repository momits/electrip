//! The user interface (Slint, ADR 0001). It is a client of the control
//! channel like any other (ADR 0010): it shows the state the host sends and
//! sends the actions of the user as commands, so it holds no logic of its
//! own (ADR 0002).

mod view;

use serde::Deserialize;
use serde_json::{Value, json};
use slint::{ComponentHandle, Image, ModelRc, SharedString, VecModel, Weak};
use std::io::{BufRead, BufReader, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

// The generated code is Slint's, not held to the rules of AGENTS.md.
#[allow(clippy::unwrap_used, clippy::panic)]
mod generated {
    slint::include_modules!();
}
use generated::*;

/// A message of the host; see `spec/steuerkanal.md`.
#[derive(Deserialize)]
struct Message {
    #[serde(rename = "type")]
    kind: String,
    state: Option<view::State>,
    error: Option<String>,
    /// Only in `hello`.
    alone: Option<String>,
}

/// How long the window tries to connect again when its connection breaks,
/// e.g. while a client instance becomes the new host (N-03).
const RECONNECT: Duration = Duration::from_secs(15);

/// The connection to the control channel; replaced when it breaks.
type Connection = Arc<Mutex<TcpStream>>;

/// Opens the window on the control channel at `address` and returns when
/// it is closed or the control channel is gone. Pictures are in `media`.
pub fn run(address: SocketAddr, media: PathBuf) -> Result<(), String> {
    let window = MainWindow::new().map_err(|e| e.to_string())?;
    let stream = TcpStream::connect(address).map_err(|e| e.to_string())?;
    let connection = Arc::new(Mutex::new(stream));
    window.set_controllers(ModelRc::new(VecModel::<Controller>::default()));
    connect_callbacks(&window, Rc::new(Arc::clone(&connection)));
    let weak = window.as_weak();
    thread::spawn(move || receive(address, &connection, weak, media));
    window.run().map_err(|e| e.to_string())
}

fn connect_callbacks(window: &MainWindow, stream: Rc<Connection>) {
    let s = Rc::clone(&stream);
    window.on_reverse(move |loco| send(&s, json!({"command": "reverse", "loco": loco})));
    let s = Rc::clone(&stream);
    window.on_toggle_sound(move |loco| send(&s, json!({"command": "toggle_sound", "loco": loco})));
    let s = Rc::clone(&stream);
    window.on_trigger(move |loco, action, pressed| {
        let command = json!({"command": "trigger_action", "loco": loco, "action": action, "pressed": pressed});
        send(&s, command)
    });
    let s = Rc::clone(&stream);
    window.on_set_view(move |auto_focus, only_active| {
        let view = json!({"auto_focus": auto_focus, "only_active": only_active});
        send(&s, json!({"command": "set_view", "view": view}))
    });
    window.on_load_picture(|path| {
        Image::load_from_path(Path::new(path.as_str())).unwrap_or_default()
    });
    let s = Rc::clone(&stream);
    window.on_set_picture(move |loco, path, x, y, width| {
        // Rounded down, the crop stays inside the image.
        let crop = json!({"x": x as u32, "y": y as u32, "width": width as u32});
        send(
            &s,
            json!({"command": "set_picture", "loco": loco, "path": path.as_str(), "crop": crop}),
        )
    });
    let s = Rc::clone(&stream);
    window.on_join_host(move |address| {
        send(
            &s,
            json!({"command": "join_host", "address": address.trim()}),
        )
    });
    let s = Rc::clone(&stream);
    window.on_set_volume(move |loco, volume| {
        send(
            &s,
            json!({"command": "set_volume", "loco": loco, "volume": volume}),
        )
    });
    let s = Rc::clone(&stream);
    window.on_set_audio_target(move |loco, target| {
        let text = |s: SharedString| (!s.is_empty()).then(|| s.to_string());
        let command = json!({"command": "set_audio_device", "loco": loco,
            "instance": text(target.instance), "device": text(target.device)});
        send(&s, command)
    });
    window.on_toggle_power(move || send(&stream, json!({"command": "toggle_power"})));
}

/// A failed command is only reported, like one from a gamepad.
fn send(connection: &Connection, command: Value) {
    let mut stream = lock(connection);
    if let Err(e) = stream.write_all(format!("{command}\n").as_bytes()) {
        eprintln!("ERROR control channel: {e}");
    }
}

fn lock(connection: &Connection) -> MutexGuard<'_, TcpStream> {
    connection.lock().unwrap_or_else(PoisonError::into_inner)
}

/// Shows each state in the window and connects again when the connection
/// breaks; closes the window when nothing arrives for [`RECONNECT`].
fn receive(address: SocketAddr, connection: &Connection, window: Weak<MainWindow>, media: PathBuf) {
    let mut last_heard = Instant::now();
    while last_heard.elapsed() < RECONNECT {
        let stream = lock(connection).try_clone();
        match stream.map(|stream| show_states(stream, &window, &media)) {
            Ok(Some(true)) => last_heard = Instant::now(),
            Ok(None) => return,
            _ => {}
        }
        thread::sleep(Duration::from_millis(500));
        if let Ok(stream) = TcpStream::connect(address) {
            *lock(connection) = stream;
        }
    }
    let _ = slint::quit_event_loop();
}

/// Shows each state until the connection breaks; returns whether a state
/// arrived, `None` if the window is closed.
fn show_states(stream: TcpStream, window: &Weak<MainWindow>, media: &Path) -> Option<bool> {
    let mut shown = false;
    for line in BufReader::new(stream).lines() {
        let message = line
            .map_err(|e| e.to_string())
            .and_then(|l| serde_json::from_str::<Message>(&l).map_err(|e| e.to_string()));
        let message = match message {
            Ok(message) => message,
            Err(e) => {
                eprintln!("ERROR control channel: {e}");
                break;
            }
        };
        if message.kind == "reply" {
            let error = message.error.unwrap_or_default();
            if !error.is_empty() {
                eprintln!("ERROR {error}");
            }
            window
                .upgrade_in_event_loop(move |w| w.set_error(error.into()))
                .ok()?;
        }
        if message.kind == "hello" {
            // Each hello, since the window may connect to a new host.
            let alone = message.alone.unwrap_or_default();
            window
                .upgrade_in_event_loop(move |w| w.set_alone(alone.into()))
                .ok()?;
        }
        if let Some(state) = message.state {
            let media = media.to_path_buf();
            window
                .upgrade_in_event_loop(move |w| view::show(&w, &state, &media))
                .ok()?;
            shown = true;
        }
    }
    Some(shown)
}
