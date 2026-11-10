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

pub use discovery::{Discovery, Status, station_id};
pub use relay::Relay;

/// Version of the message format; raised on incompatible changes.
pub const VERSION: u32 = 1;

/// How often the host handles the events of the command station and
/// drives the locos; Electrip 1 drove every 50 ms.
const POLL_INTERVAL: Duration = Duration::from_millis(50);

/// The host sends the state at least this often as a sign of life
/// (N-03); clients take it as gone after [`SILENCE`] without one.
const HEARTBEAT: Duration = Duration::from_secs(1);
const SILENCE: Duration = Duration::from_secs(3);

/// The host and all connected clients. One lock for both keeps the
/// messages to each client in order.
struct Shared {
    host: Host,
    clients: Vec<TcpStream>,
    last_poll: Instant,
    last_broadcast: Instant,
    /// Why the instance runs alone, for the window (N-03).
    alone: Option<String>,
}

/// Serves clients, each in a thread, and polls the host and the input
/// devices on the calling thread; returns only when the host state is
/// poisoned. `alone` tells the clients why other instances cannot find
/// this one.
pub fn serve(
    listener: TcpListener,
    host: Host,
    input: impl FnMut() -> Vec<Command>,
    alone: Option<String>,
) -> io::Result<()> {
    let shared = Arc::new(Mutex::new(Shared {
        host,
        clients: Vec::new(),
        last_poll: Instant::now(),
        last_broadcast: Instant::now(),
        alone,
    }));
    let acceptor = Arc::clone(&shared);
    thread::spawn(move || accept(listener, &acceptor));
    poll(&shared, input)
}

/// A failed connection is reported and does not stop the listener.
fn accept(listener: TcpListener, shared: &Arc<Mutex<Shared>>) {
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                let shared = Arc::clone(shared);
                thread::spawn(move || handle_client(stream, &shared));
            }
            Err(error) => eprintln!("ERROR control channel: {error}"),
        }
    }
}

/// Greets the client with the version and the state, then executes its
/// commands. A disconnected client ends the thread and removes its input
/// devices, so their locos do not drive on.
fn handle_client(stream: TcpStream, shared: &Mutex<Shared>) -> io::Result<()> {
    let mut devices = Vec::new();
    let result = serve_client(stream, shared, &mut devices);
    if !devices.is_empty() {
        let mut shared = lock(shared)?;
        for added in devices {
            if let Command::AddDevice { device, .. } = added {
                let _ = shared.host.apply(Command::RemoveDevice { device });
            }
        }
        shared.broadcast();
    }
    result
}

/// Executes the commands of the client and keeps `devices` up to date
/// with the input devices it added.
fn serve_client(
    stream: TcpStream,
    shared: &Mutex<Shared>,
    devices: &mut Vec<Command>,
) -> io::Result<()> {
    stream.set_nodelay(true)?;
    let mut writer = stream.try_clone()?;
    {
        let mut shared = lock(shared)?;
        send(&mut writer, &hello(shared.alone.as_deref()))?;
        send(&mut writer, &state(shared.host.session()))?;
        shared.clients.push(stream.try_clone()?);
    }
    for line in BufReader::new(stream).lines() {
        let line = line?;
        let mut shared = lock(shared)?;
        // Drives up to now first, so the command counts from its arrival.
        let polled = shared.poll();
        let result = execute(&mut shared.host, &line);
        if let Ok(command) = &result {
            track(devices, command);
        }
        send(&mut writer, &reply(&result))?;
        if result.is_ok() || polled {
            shared.broadcast();
        }
    }
    Ok(())
}

/// Keeps the `add_device` commands of the devices still connected.
fn track(devices: &mut Vec<Command>, command: &Command) {
    match command {
        Command::AddDevice { .. } => devices.push(command.clone()),
        Command::RemoveDevice { device } => devices
            .retain(|added| !matches!(added, Command::AddDevice { device: d, .. } if d == device)),
        _ => {}
    }
}

/// Executes the commands of the input devices, lets the host handle
/// station events and drive the locos, and reports changes to all clients.
/// A failed input command changes nothing, like a control without a
/// target.
fn poll(shared: &Mutex<Shared>, mut input: impl FnMut() -> Vec<Command>) -> io::Result<()> {
    loop {
        thread::sleep(POLL_INTERVAL);
        let commands = input();
        let mut shared = lock(shared)?;
        let mut changed = false;
        for command in commands {
            changed |= shared.host.apply(command).is_ok();
        }
        if shared.poll() || changed || shared.last_broadcast.elapsed() >= HEARTBEAT {
            shared.broadcast();
        }
    }
}

impl Shared {
    /// Lets the host handle the events of the command station and drive
    /// the locos for the time since the last poll; returns whether the
    /// session changed.
    fn poll(&mut self) -> bool {
        let seconds = self.last_poll.elapsed().as_secs_f64();
        self.last_poll = Instant::now();
        self.host.poll(seconds)
    }

    /// Sends the state to all clients and forgets the disconnected ones.
    fn broadcast(&mut self) {
        let state = state(self.host.session());
        self.clients.retain_mut(|c| send(c, &state).is_ok());
        self.last_broadcast = Instant::now();
    }
}

/// Reads a command from a JSON line and applies it; returns the command.
fn execute(host: &mut Host, line: &str) -> Result<Command, String> {
    let command: Command =
        serde_json::from_str(line).map_err(|e| format!("invalid command: {e}"))?;
    host.apply(command.clone()).map_err(|e| e.to_string())?;
    Ok(command)
}

fn hello(alone: Option<&str>) -> Value {
    match alone {
        Some(reason) => json!({"type": "hello", "version": VERSION, "alone": reason}),
        None => json!({"type": "hello", "version": VERSION}),
    }
}

fn reply(result: &Result<Command, String>) -> Value {
    match result {
        Ok(_) => json!({"type": "reply", "ok": true}),
        Err(error) => json!({"type": "reply", "ok": false, "error": error}),
    }
}

fn state(session: &Session) -> Value {
    json!({"type": "state", "state": session})
}

/// Writes the line at once: with Nagle's algorithm off, every write is
/// a packet of its own.
fn send(stream: &mut TcpStream, message: &Value) -> io::Result<()> {
    stream.write_all(format!("{message}\n").as_bytes())
}

fn lock(shared: &Mutex<Shared>) -> io::Result<std::sync::MutexGuard<'_, Shared>> {
    shared
        .lock()
        .map_err(|_| io::Error::other("control channel state poisoned"))
}

mod discovery;
mod relay;
#[cfg(test)]
mod tests;
