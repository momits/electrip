//! Client mode (N-03, ADR 0010): the instance has no host of its own. Its
//! control channel forwards each client to the host, and its input devices
//! send their commands there. When the host is gone, the relay switches to
//! the next host, which may be the instance itself. A host instance runs
//! behind the relay too, so it can hand over to another host. The relay
//! plays the sounds of the locos that name the instance (N-05).

use electrip_core::audio::{Audio, AudioEvent};
use electrip_core::session::Command;
use serde_json::{Value, json};
use std::collections::hash_map::RandomState;
use std::hash::BuildHasher;
use std::io::{self, BufRead, BufReader, Write};
use std::net::{Shutdown, SocketAddr, TcpListener, TcpStream};
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::Duration;

use crate::{POLL_INTERVAL, SILENCE, track};

/// How long the relay waits for the host to accept a connection.
const CONNECT_TIMEOUT: Duration = Duration::from_secs(2);

pub struct Relay {
    /// The host the clients of the control channel go to.
    target: Arc<Mutex<SocketAddr>>,
    /// The `add_device` commands of the devices still connected.
    devices: Vec<Command>,
    /// Gamepads of other instances have the same ids from SDL.
    offset: u32,
    /// The id of the instance and its audio target.
    instance: u64,
    audio: Arc<Mutex<Audio>>,
}

impl Relay {
    /// Forwards each client of `listener` to the host at `host`; the
    /// instance `instance` plays sounds on `audio`.
    pub fn start(listener: TcpListener, host: SocketAddr, instance: u64, audio: Audio) -> Relay {
        let target = Arc::new(Mutex::new(host));
        let shared = Arc::clone(&target);
        thread::spawn(move || {
            for client in listener.incoming() {
                let host = *lock(&shared);
                let upstream = TcpStream::connect_timeout(&host, CONNECT_TIMEOUT);
                match client.and_then(|client| Ok((upstream?, client))) {
                    Ok((upstream, client)) => {
                        thread::spawn(move || forward(client, upstream));
                    }
                    Err(error) => eprintln!("ERROR control channel: {error}"),
                }
            }
        });
        Relay {
            target,
            devices: Vec::new(),
            offset: (RandomState::new().hash_one(()) as u32) & 0x7fff_0000 | 0x4000_0000,
            instance,
            audio: Arc::new(Mutex::new(audio)),
        }
    }

    /// Sends the clients that connect from now on to `host`.
    pub fn switch(&self, host: SocketAddr) {
        *lock(&self.target) = host;
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

    /// Offers the audio target to the host and sends it the commands of
    /// the input devices, first those that add the devices still
    /// connected, since a new host does not know them; returns when the
    /// host is gone.
    pub fn run(&mut self, mut input: impl FnMut() -> Vec<Command>) -> io::Result<()> {
        let host = *lock(&self.target);
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
        for command in &self.devices {
            send(&stream, command, self.offset)?;
        }
        loop {
            thread::sleep(POLL_INTERVAL);
            if host_alive.is_finished() {
                return Err(io::Error::other("no sign of life"));
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

/// Copies both directions until one side closes or the host falls silent,
/// then closes the other.
fn forward(client: TcpStream, upstream: TcpStream) -> io::Result<()> {
    client.set_nodelay(true)?;
    upstream.set_nodelay(true)?;
    let (mut from_host, mut to_client) = (upstream.try_clone()?, client.try_clone()?);
    from_host.set_read_timeout(Some(SILENCE))?;
    let replies = thread::spawn(move || {
        let _ = io::copy(&mut from_host, &mut to_client);
        let _ = to_client.shutdown(Shutdown::Both);
    });
    let (mut from_client, mut to_host) = (client, upstream);
    let _ = io::copy(&mut from_client, &mut to_host);
    let _ = to_host.shutdown(Shutdown::Both);
    let _ = replies.join();
    Ok(())
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
