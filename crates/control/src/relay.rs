//! Client mode (N-03, ADR 0010): the instance has no host of its own. Its
//! control channel forwards each client to the host, and its input devices
//! send their commands there. When the host is gone, the relay switches to
//! the next host, which may be the instance itself. A host instance runs
//! behind the relay too, so it can hand over to another host. A client
//! instance joins another host on `join_host` by itself, its host stays.
//! The relay plays the sounds of the locos that name the instance (N-05).
//! A client instance drives with its own configuration as a guest of the
//! host (Q-016).

use electrip_core::audio::{Audio, AudioEvent};
use electrip_core::config::Config;
use electrip_core::session::Command;
use serde_json::{Value, json};
use std::collections::hash_map::RandomState;
use std::hash::BuildHasher;
use std::io::{self, BufRead, BufReader, Write};
use std::net::{Shutdown, SocketAddr, TcpListener, TcpStream};
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::Duration;

use crate::{POLL_INTERVAL, SILENCE, join, join_request, reply, track};

/// How long the relay waits for the host to accept a connection.
const CONNECT_TIMEOUT: Duration = Duration::from_secs(2);

pub struct Relay {
    route: Arc<Mutex<Route>>,
    /// The control channel, until the relay knows where its clients go.
    listener: Option<TcpListener>,
    /// The `add_device` commands of the devices still connected.
    devices: Vec<Command>,
    /// Gamepads of other instances have the same ids from SDL.
    offset: u32,
    /// The id of the instance and its audio target.
    instance: u64,
    audio: Arc<Mutex<Audio>>,
}

/// Where the clients of the control channel go (N-03).
struct Route {
    host: SocketAddr,
    /// Whether the instance is client of the host; else it is the host
    /// and handles `join_host` itself.
    client: bool,
    /// The host a client asked to join, until the relay runs there.
    joined: Option<SocketAddr>,
    /// The connections of the clients, closed when the instance joins.
    clients: Vec<TcpStream>,
    /// The configuration the instance drives with while it is client.
    configuration: Option<Config>,
}

impl Route {
    /// Sends the clients to `host` from now on and closes the connections
    /// of the old host, so they connect again.
    fn join(&mut self, host: SocketAddr) {
        self.host = host;
        self.joined = Some(host);
        for client in self.clients.drain(..) {
            let _ = client.shutdown(Shutdown::Both);
        }
    }

    /// The `use_configuration` request a connection to the host starts
    /// with while the instance is client; the host keeps the connection
    /// if it has the configuration open itself.
    fn guest_request(&self) -> Option<Value> {
        let config = self.configuration.as_ref().filter(|_| self.client)?;
        Some(json!({"command": "use_configuration", "configuration": config}))
    }
}

impl Relay {
    /// A relay to the host at `host` that forwards the clients of
    /// `listener` from the first [`Relay::switch`] on; the instance
    /// `instance` plays sounds on `audio`.
    pub fn new(listener: TcpListener, host: SocketAddr, instance: u64, audio: Audio) -> Relay {
        let route = Arc::new(Mutex::new(Route {
            host,
            client: false,
            joined: None,
            clients: Vec::new(),
            configuration: None,
        }));
        Relay {
            route,
            listener: Some(listener),
            devices: Vec::new(),
            offset: (RandomState::new().hash_one(()) as u32) & 0x7fff_0000 | 0x4000_0000,
            instance,
            audio: Arc::new(Mutex::new(audio)),
        }
    }

    /// Sends the clients that connect from now on to `host`; `client`
    /// tells whether the instance is client of it. The first switch
    /// starts to forward the clients, so none reaches the host before the
    /// relay knows the configuration of the instance.
    pub fn switch(&mut self, host: SocketAddr, client: bool) {
        let mut route = lock(&self.route);
        (route.host, route.client) = (host, client);
        if let Some(listener) = self.listener.take() {
            let route = Arc::clone(&self.route);
            thread::spawn(move || accept(listener, &route));
        }
    }

    /// Drives with `configuration` while the instance is client, on the
    /// connections to the host from now on.
    pub fn drive_with(&self, configuration: Option<Config>) {
        lock(&self.route).configuration = configuration;
    }

    /// The host a client asked to join, once.
    pub fn joined(&self) -> Option<SocketAddr> {
        lock(&self.route).joined.take()
    }

    /// The `add_device` commands of the devices still connected.
    pub fn devices(&self) -> &[Command] {
        &self.devices
    }

    /// Keeps the devices of `commands`, so the next host knows them,
    /// also while the instance is host itself.
    pub fn track(&mut self, commands: Vec<Command>) -> Vec<Command> {
        for command in &commands {
            track(&mut self.devices, command);
        }
        commands
    }

    /// Offers the audio target to the host, drives with the configuration
    /// of the instance and sends the host the commands of the input
    /// devices, first those that add the devices still
    /// connected, since a new host does not know them; returns when the
    /// host is gone, or when a client asked to join another one.
    pub fn run(&mut self, mut input: impl FnMut() -> Vec<Command>) -> io::Result<()> {
        let host = lock(&self.route).host;
        let stream = TcpStream::connect_timeout(&host, CONNECT_TIMEOUT)?;
        stream.set_nodelay(true)?;
        // Reads all messages, so the host never waits to write them; it
        // ends when the host is gone or falls silent.
        let replies = stream.try_clone()?;
        replies.set_read_timeout(Some(SILENCE))?;
        // Both threads write to the host.
        let stream = Arc::new(Mutex::new(stream));
        let (audio, pongs) = (Arc::clone(&self.audio), Arc::clone(&stream));
        let host_alive = thread::spawn(move || play(replies, &pongs, &audio));
        let devices = lock(&self.audio).devices();
        let offer = json!({
            "command": "offer_audio",
            "instance": format!("{:016x}", self.instance),
            "devices": devices,
        });
        write(&stream, &offer)?;
        let guest = lock(&self.route).guest_request();
        if let Some(request) = guest {
            write(&stream, &request)?;
        }
        for command in &self.devices {
            send(&stream, command, self.offset)?;
        }
        loop {
            thread::sleep(POLL_INTERVAL);
            if host_alive.is_finished() {
                return Err(io::Error::other("no sign of life"));
            }
            if lock(&self.route).joined.is_some() {
                return Ok(());
            }
            for command in self.track(input()) {
                send(&stream, &command, self.offset)?;
            }
        }
    }
}

fn lock<T>(mutex: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex.lock().unwrap_or_else(PoisonError::into_inner)
}

/// Plays the audio events among the messages of the host and answers its
/// pings until it is gone or falls silent; an event it does not know is
/// left out.
fn play(replies: TcpStream, host: &Mutex<TcpStream>, audio: &Mutex<Audio>) -> io::Result<()> {
    for line in BufReader::new(replies).lines() {
        let message: Value = serde_json::from_str(&line?)?;
        if message["type"] == "ping" {
            write(host, &json!({"command": "pong"}))?;
        }
        if message["type"] != "audio" {
            continue;
        }
        match serde_json::from_value::<AudioEvent>(message["audio"].clone()) {
            Ok(event) => event.apply(&mut **lock(audio)),
            Err(e) => eprintln!("ERROR unknown audio event {}: {e}", message["audio"]),
        }
    }
    Ok(())
}

fn send(stream: &Mutex<TcpStream>, command: &Command, offset: u32) -> io::Result<()> {
    write(
        stream,
        &serde_json::to_value(offset_device(command.clone(), offset))?,
    )
}

fn write(stream: &Mutex<TcpStream>, message: &Value) -> io::Result<()> {
    lock(stream).write_all(format!("{message}\n").as_bytes())
}

/// Forwards each client of `listener` to the host of the `route`.
fn accept(listener: TcpListener, route: &Arc<Mutex<Route>>) {
    for client in listener.incoming() {
        let host = lock(route).host;
        let upstream = TcpStream::connect_timeout(&host, CONNECT_TIMEOUT);
        match client.and_then(|client| Ok((upstream?, client))) {
            Ok((upstream, client)) => {
                let route = Arc::clone(route);
                thread::spawn(move || forward(client, upstream, &route));
            }
            Err(error) => eprintln!("ERROR control channel: {error}"),
        }
    }
}

/// Copies the lines of both directions until one side closes or the host
/// falls silent, then closes the other. While the instance is client, it
/// answers `join_host` itself.
fn forward(client: TcpStream, upstream: TcpStream, route: &Mutex<Route>) -> io::Result<()> {
    let peer = client.peer_addr()?;
    lock(route).clients.push(client.try_clone()?);
    let result = copy_lines(client, upstream, route);
    lock(route)
        .clients
        .retain(|c| c.peer_addr().is_ok_and(|a| a != peer));
    result
}

fn copy_lines(client: TcpStream, upstream: TcpStream, route: &Mutex<Route>) -> io::Result<()> {
    client.set_nodelay(true)?;
    upstream.set_nodelay(true)?;
    let mut from_host = BufReader::new(upstream.try_clone()?);
    from_host.get_ref().set_read_timeout(Some(SILENCE))?;
    let mut hello = String::new();
    from_host.read_line(&mut hello)?;
    let host_id = serde_json::from_str::<Value>(&hello)?["id"].clone();
    let mut to_host = upstream;
    // Without the lock while it waits for the host.
    let guest = lock(route).guest_request();
    if let Some(request) = guest {
        to_host.write_all(format!("{request}\n").as_bytes())?;
        skip_to_reply(&mut from_host)?;
    }
    let to_client = Arc::new(Mutex::new(client.try_clone()?));
    lock(&to_client).write_all(hello.as_bytes())?;
    let writer = Arc::clone(&to_client);
    let replies = thread::spawn(move || {
        for line in from_host.lines().map_while(Result::ok) {
            if lock(&writer)
                .write_all(format!("{line}\n").as_bytes())
                .is_err()
            {
                break;
            }
        }
        let _ = lock(&writer).shutdown(Shutdown::Both);
    });
    for line in BufReader::new(client).lines().map_while(Result::ok) {
        match join_request(&line).filter(|_| lock(route).client) {
            Some(address) => {
                let result = join(&address, host_id.as_str().unwrap_or_default());
                write(&to_client, &reply(&result))?;
                if let Ok(host) = result {
                    lock(route).join(host);
                }
            }
            None => to_host.write_all(format!("{line}\n").as_bytes())?,
        }
    }
    let _ = to_host.shutdown(Shutdown::Both);
    let _ = replies.join();
    Ok(())
}

/// Skips the messages of the host up to the reply, so the client gets
/// the state of the guest only and no reply it did not ask for.
fn skip_to_reply(from_host: &mut BufReader<TcpStream>) -> io::Result<()> {
    let mut line = String::new();
    loop {
        line.clear();
        if from_host.read_line(&mut line)? == 0 {
            return Err(io::ErrorKind::UnexpectedEof.into());
        }
        let message: Value = serde_json::from_str(&line)?;
        if message["type"] == "reply" {
            if let Some(error) = message["error"].as_str() {
                eprintln!("ERROR the host drives without the configuration: {error}");
            }
            return Ok(());
        }
    }
}

fn offset_device(mut command: Command, offset: u32) -> Command {
    if let Command::AddDevice { device, .. }
    | Command::RemoveDevice { device }
    | Command::Input { device, .. } = &mut command
    {
        *device |= offset;
    }
    command
}
