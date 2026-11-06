//! The user interface (Slint, ADR 0001). It is a client of the control
//! channel like any other (ADR 0010): it shows the state the host sends and
//! sends the actions of the user as commands, so it holds no logic of its
//! own (ADR 0002).

mod view;

use serde::Deserialize;
use serde_json::{Value, json};
use slint::{ComponentHandle, ModelRc, VecModel, Weak};
use std::io::{BufRead, BufReader, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::rc::Rc;
use std::thread;

// The generated code is Slint's, not held to the rules of AGENTS.md.
#[allow(clippy::unwrap_used, clippy::panic)]
mod generated {
    slint::include_modules!();
}
use generated::*;

/// A message of the host; see `spec/steuerkanal.md`.
#[derive(Deserialize)]
struct Message {
    state: Option<view::State>,
    error: Option<String>,
}

/// Opens the window on the control channel at `address` and returns when
/// it is closed or the host is gone. Pictures are in `media`.
pub fn run(address: SocketAddr, media: PathBuf) -> Result<(), String> {
    let window = MainWindow::new().map_err(|e| e.to_string())?;
    let stream = TcpStream::connect(address).map_err(|e| e.to_string())?;
    let reader = stream.try_clone().map_err(|e| e.to_string())?;
    window.set_controllers(ModelRc::new(VecModel::<Controller>::default()));
    connect_callbacks(&window, Rc::new(stream));
    let weak = window.as_weak();
    thread::spawn(move || receive(reader, weak, media));
    window.run().map_err(|e| e.to_string())
}

fn connect_callbacks(window: &MainWindow, stream: Rc<TcpStream>) {
    let s = Rc::clone(&stream);
    window.on_reverse(move |loco| send(&s, json!({"command": "reverse", "loco": loco})));
    let s = Rc::clone(&stream);
    window.on_toggle_sound(move |loco| send(&s, json!({"command": "toggle_sound", "loco": loco})));
    let s = Rc::clone(&stream);
    window.on_trigger(move |loco, action, pressed| {
        let command = json!({"command": "trigger_action", "loco": loco, "action": action, "pressed": pressed});
        send(&s, command)
    });
    window.on_toggle_power(move || send(&stream, json!({"command": "toggle_power"})));
}

/// A failed command is only reported, like one from a gamepad.
fn send(mut stream: &TcpStream, command: Value) {
    if let Err(e) = writeln!(stream, "{command}") {
        eprintln!("ERROR control channel: {e}");
    }
}

/// Shows each state in the window; closes it when the host is gone.
fn receive(stream: TcpStream, window: Weak<MainWindow>, media: PathBuf) {
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
        if let Some(error) = message.error {
            eprintln!("ERROR {error}");
        }
        if let Some(state) = message.state {
            let media = media.clone();
            let shown = window.upgrade_in_event_loop(move |w| view::show(&w, &state, &media));
            if shown.is_err() {
                return;
            }
        }
    }
    let _ = slint::quit_event_loop();
}
