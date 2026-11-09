//! Client mode (N-03, ADR 0010): the instance has no host of its own. Its
//! control channel forwards each client to the host, and its input devices
//! send their commands there. When the host is gone, the relay switches to
//! the next host, which may be the instance itself.

use electrip_core::session::Command;
use std::collections::hash_map::RandomState;
use std::hash::BuildHasher;
use std::io::{self, Write};
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
}

impl Relay {
    /// Forwards each client of `listener` to the host at `host`.
    pub fn start(listener: TcpListener, host: SocketAddr) -> Relay {
        let target = Arc::new(Mutex::new(host));
        let current = Arc::clone(&target);
        thread::spawn(move || {
            for client in listener.incoming() {
                let host = *current.lock().unwrap_or_else(PoisonError::into_inner);
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
        }
    }

    /// Sends the clients that connect from now on to `host`.
    pub fn switch(&self, host: SocketAddr) {
        *self.target.lock().unwrap_or_else(PoisonError::into_inner) = host;
    }

    /// The `add_device` commands of the devices still connected.
    pub fn devices(&self) -> &[Command] {
        &self.devices
    }

    /// Sends the commands of the input devices to the host, first those
    /// that add the devices still connected, since a new host does not know
    /// them; returns when the host is gone.
    pub fn run(&mut self, mut input: impl FnMut() -> Vec<Command>) -> io::Result<()> {
        let host = *self.target.lock().unwrap_or_else(PoisonError::into_inner);
        let mut stream = TcpStream::connect_timeout(&host, CONNECT_TIMEOUT)?;
        // Drains the replies and states, so the host never waits to write
        // them; it ends when the host is gone or falls silent.
        let mut replies = stream.try_clone()?;
        replies.set_read_timeout(Some(SILENCE))?;
        let host_alive = thread::spawn(move || io::copy(&mut replies, &mut io::sink()));
        for command in &self.devices {
            send(&mut stream, command, self.offset)?;
        }
        loop {
            thread::sleep(POLL_INTERVAL);
            if host_alive.is_finished() {
                return Err(io::Error::other("no sign of life"));
            }
            for command in input() {
                track(&mut self.devices, &command);
                send(&mut stream, &command, self.offset)?;
            }
        }
    }
}

fn send(stream: &mut TcpStream, command: &Command, offset: u32) -> io::Result<()> {
    let command = serde_json::to_string(&offset_device(command.clone(), offset))?;
    writeln!(stream, "{command}")
}

/// Copies both directions until one side closes or the host falls silent,
/// then closes the other.
fn forward(client: TcpStream, upstream: TcpStream) -> io::Result<()> {
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
