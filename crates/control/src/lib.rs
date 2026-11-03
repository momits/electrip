//! Local JSON control channel (N-08, ADR 0002): clients send commands and
//! receive the state, one JSON message per line. The format is described in
//! `spec/steuerkanal.md`.

use electrip_core::host::Host;
use electrip_core::session::{Command, Session};
use serde_json::{Value, json};
use std::io::{self, BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

/// Version of the message format; raised on incompatible changes.
pub const VERSION: u32 = 1;

/// How often the host handles the events of the command station and
/// drives the locos; Electrip 1 drove every 50 ms.
const POLL_INTERVAL: Duration = Duration::from_millis(50);

/// The host and all connected clients. One lock for both keeps the
/// messages to each client in order.
struct Shared {
    host: Host,
    clients: Vec<TcpStream>,
}

/// Serves clients, each in a thread, and polls the host and the input
/// devices on the calling thread; returns only on an error.
pub fn serve(
    listener: TcpListener,
    host: Host,
    input: impl FnMut() -> Vec<Command>,
) -> io::Result<()> {
    let shared = Arc::new(Mutex::new(Shared {
        host,
        clients: Vec::new(),
    }));
    let acceptor = Arc::clone(&shared);
    thread::spawn(move || accept(listener, &acceptor));
    poll(&shared, input)
}

fn accept(listener: TcpListener, shared: &Arc<Mutex<Shared>>) -> io::Result<()> {
    for stream in listener.incoming() {
        let shared = Arc::clone(shared);
        thread::spawn(move || handle_client(stream?, &shared));
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
        send(&mut writer, &state(shared.host.session()))?;
        shared.clients.push(stream.try_clone()?);
    }
    for line in BufReader::new(stream).lines() {
        let line = line?;
        let mut shared = lock(shared)?;
        let result = execute(&mut shared.host, &line);
        send(&mut writer, &reply(&result))?;
        if result.is_ok() {
            shared.broadcast();
        }
    }
    Ok(())
}

/// Executes the commands of the input devices, lets the host handle
/// station events and drive the locos, and reports changes to all clients.
/// A failed input command changes nothing, like a control without a
/// target.
fn poll(shared: &Mutex<Shared>, mut input: impl FnMut() -> Vec<Command>) -> io::Result<()> {
    let mut last = Instant::now();
    loop {
        thread::sleep(POLL_INTERVAL);
        let commands = input();
        let mut shared = lock(shared)?;
        let mut changed = false;
        for command in commands {
            changed |= shared.host.apply(command).is_ok();
        }
        let seconds = last.elapsed().as_secs_f64();
        last = Instant::now();
        if shared.host.poll(seconds) || changed {
            shared.broadcast();
        }
    }
}

impl Shared {
    /// Sends the state to all clients and forgets the disconnected ones.
    fn broadcast(&mut self) {
        let state = state(self.host.session());
        self.clients.retain_mut(|c| send(c, &state).is_ok());
    }
}

/// Reads a command from a JSON line and applies it.
fn execute(host: &mut Host, line: &str) -> Result<(), String> {
    let command: Command =
        serde_json::from_str(line).map_err(|e| format!("invalid command: {e}"))?;
    host.apply(command).map_err(|e| e.to_string())
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
