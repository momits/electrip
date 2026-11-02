//! Local JSON control channel (N-08, ADR 0002): clients send commands and
//! receive the state, one JSON message per line. The format is described in
//! `spec/steuerkanal.md`.

use electrip_core::session::{Command, Session};
use serde_json::{Value, json};
use std::io::{self, BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Arc, Mutex};
use std::thread;

/// Version of the message format; raised on incompatible changes.
pub const VERSION: u32 = 1;

/// The session and all connected clients. One lock for both keeps the
/// messages to each client in order.
#[derive(Default)]
struct Shared {
    session: Session,
    clients: Vec<TcpStream>,
}

/// Serves clients until the listener fails; each client gets a thread.
pub fn serve(listener: TcpListener) -> io::Result<()> {
    let shared = Arc::new(Mutex::new(Shared::default()));
    for stream in listener.incoming() {
        let stream = stream?;
        let shared = Arc::clone(&shared);
        thread::spawn(move || handle_client(stream, &shared));
    }
    Ok(())
}

/// Greets the client with the version and the state, then executes its
/// commands. A disconnected client ends the thread.
fn handle_client(stream: TcpStream, shared: &Mutex<Shared>) -> io::Result<()> {
    let mut writer = stream.try_clone()?;
    {
        let mut shared = lock(shared)?;
        send(&mut writer, &json!({"type": "hello", "version": VERSION}))?;
        send(&mut writer, &state(&shared.session))?;
        shared.clients.push(stream.try_clone()?);
    }
    for line in BufReader::new(stream).lines() {
        let line = line?;
        let mut shared = lock(shared)?;
        let result = execute(&mut shared.session, &line);
        send(&mut writer, &reply(&result))?;
        if result.is_ok() {
            let state = state(&shared.session);
            shared.clients.retain_mut(|c| send(c, &state).is_ok());
        }
    }
    Ok(())
}

/// Reads a command from a JSON line and applies it to the session.
fn execute(session: &mut Session, line: &str) -> Result<(), String> {
    let command: Command =
        serde_json::from_str(line).map_err(|e| format!("invalid command: {e}"))?;
    session.apply(command).map_err(|e| e.to_string())
}

fn reply(result: &Result<(), String>) -> Value {
    match result {
        Ok(()) => json!({"type": "reply", "ok": true}),
        Err(error) => json!({"type": "reply", "ok": false, "error": error}),
    }
}

fn state(session: &Session) -> Value {
    json!({"type": "state", "state": session})
}

fn send(stream: &mut TcpStream, message: &Value) -> io::Result<()> {
    writeln!(stream, "{message}")
}

fn lock(shared: &Mutex<Shared>) -> io::Result<std::sync::MutexGuard<'_, Shared>> {
    shared
        .lock()
        .map_err(|_| io::Error::other("control channel state poisoned"))
}

#[cfg(test)]
mod tests;
