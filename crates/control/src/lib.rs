//! Local JSON control channel (N-08, ADR 0002): clients send commands and
//! receive the state, one JSON message per line. The format is described in
//! `spec/steuerkanal.md`.

use electrip_core::audio::AudioEvent;
use electrip_core::host::Host;
use electrip_core::session::{Command, Session};
use serde_json::{Value, json};
use std::collections::HashMap;
use std::collections::hash_map::RandomState;
use std::fs;
use std::hash::BuildHasher;
use std::io::{self, BufRead, BufReader, Write};
use std::net::{Shutdown, SocketAddr, TcpListener, TcpStream, ToSocketAddrs};
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

pub use discovery::{Discovery, Status, station_id};
pub use relay::Relay;
pub use sync::sync;

/// Version of the message format; raised on incompatible changes.
pub const VERSION: u32 = 1;

/// The port of the control channel unless set otherwise.
pub const DEFAULT_PORT: u16 = 4711;

/// How long a host has to answer (N-03).
pub const HOST_TIMEOUT: Duration = Duration::from_secs(2);

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
    clients: Vec<Client>,
    last_poll: Instant,
    last_broadcast: Instant,
    /// Why the instance runs alone, for the window (N-03).
    alone: Option<String>,
    /// The instance id in `hello`, so the host does not join itself.
    id: String,
    /// The host to join, as a client asked (N-03).
    joined: Option<SocketAddr>,
    /// The host handed over to another one; no client gets in any more.
    stopped: bool,
    /// The connection of each instance that plays sounds (N-05); one that
    /// reconnects may offer before its old connection is closed.
    offers: HashMap<String, Offer>,
}

/// A connection that gets the state.
struct Client {
    stream: TcpStream,
    address: SocketAddr,
}

/// An instance that plays sounds and the ping that measures the round
/// trip to it (N-05).
struct Offer {
    address: SocketAddr,
    client: TcpStream,
    /// When the next ping goes out.
    next: Instant,
    /// When the ping whose pong is still missing went out.
    pending: Option<Instant>,
}

/// The id of the instance with the library, the same after a restart; a
/// new library gets a random one (N-05).
pub fn instance_id(library: &Path) -> io::Result<u64> {
    let file = library.join("instance");
    let saved = fs::read_to_string(&file).ok();
    if let Some(id) = saved.and_then(|id| u64::from_str_radix(id.trim(), 16).ok()) {
        return Ok(id);
    }
    // A random number without a further dependency.
    let id = RandomState::new().hash_one(());
    fs::create_dir_all(library)?;
    fs::write(file, format!("{id:016x}"))?;
    Ok(id)
}

/// Serves clients, each in a thread, and polls the host and the input
/// devices on the calling thread; `id` is the instance id. `alone` tells
/// the clients why other instances cannot find this one. When `handover` names another host,
/// or a client asks to join one, it closes all connections and returns
/// that host (N-03); the host is dropped when their threads end.
pub fn serve(
    listener: TcpListener,
    host: Host,
    id: u64,
    input: impl FnMut() -> Vec<Command>,
    alone: Option<String>,
    handover: impl FnMut() -> Option<SocketAddr>,
) -> io::Result<SocketAddr> {
    let address = listener.local_addr()?;
    let shared = Arc::new(Mutex::new(Shared {
        host,
        clients: Vec::new(),
        last_poll: Instant::now(),
        last_broadcast: Instant::now(),
        alone,
        id: format!("{id:016x}"),
        joined: None,
        stopped: false,
        offers: HashMap::new(),
    }));
    let acceptor = Arc::clone(&shared);
    thread::spawn(move || accept(listener, &acceptor));
    let next = poll(&shared, input, handover)?;
    lock(&shared)?.stop();
    // Wakes the acceptor, so it ends and drops the host.
    let _ = TcpStream::connect(address)
        .inspect_err(|e| eprintln!("ERROR the old host stays open: {e}"));
    Ok(next)
}

/// A failed connection is reported and does not stop the listener; ends
/// when the host is stopped.
fn accept(listener: TcpListener, shared: &Arc<Mutex<Shared>>) {
    for stream in listener.incoming() {
        if lock(shared).map_or(true, |shared| shared.stopped) {
            return;
        }
        match stream {
            Ok(stream) => {
                let shared = Arc::clone(shared);
                thread::spawn(move || handle_client(stream, &shared));
            }
            Err(error) => eprintln!("ERROR control channel: {error}"),
        }
    }
}

/// What a client added to the host.
#[derive(Default)]
struct Added {
    /// The `add_device` commands of its input devices.
    devices: Vec<Command>,
    /// Its instance and address, if it plays sounds (N-05).
    audio: Option<(String, SocketAddr)>,
}

/// Greets the client with the version and the state, then executes its
/// commands. A disconnected client ends the thread and removes its input
/// devices, so their locos do not drive on, and its audio target.
fn handle_client(stream: TcpStream, shared: &Mutex<Shared>) -> io::Result<()> {
    let address = stream.peer_addr()?;
    let mut added = Added::default();
    let result = serve_client(stream, address, shared, &mut added);
    let mut shared = lock(shared)?;
    shared.leave(added.devices);
    shared.clients.retain(|c| c.address != address);
    if let Some((instance, address)) = added.audio
        && shared.offers.get(&instance).map(|o| o.address) == Some(address)
    {
        shared.offers.remove(&instance);
        shared.host.remove_audio_target(&instance);
    }
    shared.broadcast();
    result
}

/// Executes the commands of the client and keeps `added` up to date.
fn serve_client(
    stream: TcpStream,
    address: SocketAddr,
    shared: &Mutex<Shared>,
    added: &mut Added,
) -> io::Result<()> {
    stream.set_nodelay(true)?;
    let mut writer = stream.try_clone()?;
    {
        let mut shared = lock(shared)?;
        if shared.stopped {
            return Ok(());
        }
        send(&mut writer, &hello(&shared.id, shared.alone.as_deref()))?;
        send(&mut writer, &state(shared.host.session()))?;
        shared.clients.push(Client {
            stream: stream.try_clone()?,
            address,
        });
    }
    for line in BufReader::new(stream).lines() {
        let line = line?;
        if let Some(address) = join_request(&line) {
            // Without the lock while it waits for the other host.
            let id = lock(shared)?.id.clone();
            let result = join(&address, &id);
            let mut shared = lock(shared)?;
            send(&mut writer, &reply(&result))?;
            shared.joined = result.ok();
            continue;
        }
        if let Some((instance, devices)) = offer_request(&line) {
            added.audio = Some((instance.clone(), address));
            let mut shared = lock(shared)?;
            let offer = Offer {
                address,
                client: writer.try_clone()?,
                next: Instant::now(),
                pending: None,
            };
            shared.offers.insert(instance.clone(), offer);
            offer_audio(&mut shared.host, instance, devices, writer.try_clone()?);
            send(&mut writer, &reply(&Ok::<(), String>(())))?;
            shared.broadcast();
            continue;
        }
        if is_pong(&line) {
            if let Some((instance, address)) = &added.audio {
                lock(shared)?.pong(instance, *address);
            }
            continue;
        }
        let mut shared = lock(shared)?;
        // Drives up to now first, so the command counts from its arrival.
        let polled = shared.poll();
        let result = sync::answer(&mut shared.host, &line).unwrap_or_else(|| {
            let command = execute(&mut shared.host, &line)?;
            track(&mut added.devices, &command);
            Ok(json!({}))
        });
        let ok = result.is_ok();
        let message = reply_with(result);
        send(&mut writer, &message)?;
        if ok || polled {
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
/// target. Returns the host to hand over to.
fn poll(
    shared: &Mutex<Shared>,
    mut input: impl FnMut() -> Vec<Command>,
    mut handover: impl FnMut() -> Option<SocketAddr>,
) -> io::Result<SocketAddr> {
    loop {
        thread::sleep(POLL_INTERVAL);
        if let Some(next) = handover() {
            return Ok(next);
        }
        let commands = input();
        let mut shared = lock(shared)?;
        if let Some(next) = shared.joined.take() {
            return Ok(next);
        }
        let mut changed = false;
        for command in commands {
            changed |= shared.host.apply(command).is_ok();
        }
        if shared.poll() || changed || shared.last_broadcast.elapsed() >= HEARTBEAT {
            shared.broadcast();
        }
        shared.ping();
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

    /// Sends each client the state and forgets the disconnected ones.
    fn broadcast(&mut self) {
        let state = state(self.host.session());
        self.clients
            .retain_mut(|c| send(&mut c.stream, &state).is_ok());
        self.last_broadcast = Instant::now();
    }

    /// Removes the input `devices` a client added.
    fn leave(&mut self, devices: Vec<Command>) {
        for command in devices {
            if let Command::AddDevice { device, .. } = command {
                let _ = self.host.apply(Command::RemoveDevice { device });
            }
        }
    }

    /// Pings each instance that plays sounds once a heartbeat, unless its
    /// pong is still missing (N-05).
    fn ping(&mut self) {
        let now = Instant::now();
        for offer in self.offers.values_mut() {
            if offer.pending.is_none() && offer.next <= now {
                offer.pending = Some(now);
                let _ = send(&mut offer.client, &json!({"type": "ping"}));
            }
        }
    }

    /// Takes the round trip of the ping to `instance` on the connection
    /// from `address`.
    fn pong(&mut self, instance: &str, address: SocketAddr) {
        let Some(offer) = self
            .offers
            .get_mut(instance)
            .filter(|o| o.address == address)
        else {
            return;
        };
        if let Some(sent) = offer.pending.take() {
            offer.next = Instant::now() + HEARTBEAT;
            self.host.set_audio_latency(instance, sent.elapsed());
        }
    }

    /// Closes the connections of all clients, so they find the next host.
    fn stop(&mut self) {
        self.stopped = true;
        for client in self.clients.drain(..) {
            let _ = client.stream.shutdown(Shutdown::Both);
        }
    }
}

/// The address of a `join_host` request; the host handles it itself, it
/// is no command of the session.
fn join_request(line: &str) -> Option<String> {
    let request: Value = serde_json::from_str(line).ok()?;
    if request["command"] != "join_host" {
        return None;
    }
    request["address"].as_str().map(String::from)
}

/// The instance and its output devices of an `offer_audio` request: it
/// offers to play the sounds of the locos that name it (N-05). The host
/// handles it itself, since the audio events go back on the connection.
fn offer_request(line: &str) -> Option<(String, Vec<String>)> {
    let request: Value = serde_json::from_str(line).ok()?;
    if request["command"] != "offer_audio" {
        return None;
    }
    let instance = request["instance"].as_str()?.to_string();
    let devices = serde_json::from_value(request["devices"].clone()).ok()?;
    Some((instance, devices))
}

/// Whether the line is the answer of an instance to a ping (N-05).
fn is_pong(line: &str) -> bool {
    serde_json::from_str::<Value>(line).is_ok_and(|request| request["command"] == "pong")
}

/// Sends the audio events of the locos that name the instance to the
/// client.
fn offer_audio(host: &mut Host, instance: String, devices: Vec<String>, mut client: TcpStream) {
    let remote = Box::new(move |event: &AudioEvent| {
        send(&mut client, &json!({"type": "audio", "audio": event})).is_ok()
    });
    host.add_audio_target(instance, devices, remote);
}

/// The host at `address` if it greets with another id than `id`: with
/// the same, it is this host or a client of it.
fn join(address: &str, id: &str) -> Result<SocketAddr, String> {
    let (host, hello) =
        find_host(address).map_err(|e| format!("cannot reach the host {address}: {e}"))?;
    if hello["id"] == id {
        return Err(format!("{address} is already in this session"));
    }
    Ok(host)
}

/// The first address of `address` with a host that greets, and its
/// `hello`; the port defaults to [`DEFAULT_PORT`].
pub fn find_host(address: &str) -> io::Result<(SocketAddr, Value)> {
    let addresses = address
        .to_socket_addrs()
        .or_else(|_| (address, DEFAULT_PORT).to_socket_addrs())?;
    let mut error = io::Error::other("no address");
    for host in addresses {
        match greeting(host) {
            Ok(hello) => return Ok((host, hello)),
            Err(e) => error = e,
        }
    }
    Err(error)
}

/// The first message of the host at `host`.
fn greeting(host: SocketAddr) -> io::Result<Value> {
    let stream = TcpStream::connect_timeout(&host, HOST_TIMEOUT)?;
    stream.set_read_timeout(Some(HOST_TIMEOUT))?;
    let line = BufReader::new(stream)
        .lines()
        .next()
        .unwrap_or_else(|| Err(io::Error::other("no greeting")))?;
    Ok(serde_json::from_str(&line)?)
}

/// Reads a command from a JSON line and applies it; returns the command.
fn execute(host: &mut Host, line: &str) -> Result<Command, String> {
    let command: Command =
        serde_json::from_str(line).map_err(|e| format!("invalid command: {e}"))?;
    host.apply(command.clone()).map_err(|e| e.to_string())?;
    Ok(command)
}

fn hello(id: &str, alone: Option<&str>) -> Value {
    let mut hello = json!({"type": "hello", "version": VERSION, "id": id});
    if let Some(reason) = alone {
        hello["alone"] = reason.into();
    }
    hello
}

fn reply<T>(result: &Result<T, String>) -> Value {
    match result {
        Ok(_) => json!({"type": "reply", "ok": true}),
        Err(error) => json!({"type": "reply", "ok": false, "error": error}),
    }
}

/// The reply with the `fields` of a successful request.
fn reply_with(result: Result<Value, String>) -> Value {
    let mut message = reply(&result);
    if let (Ok(Value::Object(fields)), Some(reply)) = (result, message.as_object_mut()) {
        reply.extend(fields);
    }
    message
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
mod sync;
#[cfg(test)]
mod tests;
