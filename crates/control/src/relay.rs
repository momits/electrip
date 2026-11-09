//! Client mode (N-03, ADR 0010): the instance has no host of its own. Its
//! control channel forwards each client to the host, and its input devices
//! send their commands there.

use electrip_core::session::Command;
use std::collections::hash_map::RandomState;
use std::hash::BuildHasher;
use std::io::{self, Write};
use std::net::{Shutdown, SocketAddr, TcpListener, TcpStream};
use std::thread;

use crate::POLL_INTERVAL;

/// Forwards the clients of `listener` to the host at `host` and sends the
/// commands of the input devices there; returns when the host is gone.
pub fn relay(
    listener: TcpListener,
    host: SocketAddr,
    mut input: impl FnMut() -> Vec<Command>,
) -> io::Result<()> {
    thread::spawn(move || {
        for client in listener.incoming() {
            match client.and_then(|client| Ok((TcpStream::connect(host)?, client))) {
                Ok((upstream, client)) => {
                    thread::spawn(move || forward(client, upstream));
                }
                Err(error) => eprintln!("ERROR control channel: {error}"),
            }
        }
    });
    let mut stream = TcpStream::connect(host)?;
    // Only the host answers; its replies and states are not needed here.
    let mut replies = stream.try_clone()?;
    thread::spawn(move || io::copy(&mut replies, &mut io::sink()));
    // Gamepads of other instances have the same ids from SDL.
    let offset = (RandomState::new().hash_one(host) as u32) & 0x7fff_0000 | 0x4000_0000;
    loop {
        thread::sleep(POLL_INTERVAL);
        for command in input() {
            let command = serde_json::to_string(&offset_device(command, offset))?;
            writeln!(stream, "{command}")?;
        }
    }
}

/// Copies both directions until one side closes, then closes the other.
fn forward(client: TcpStream, upstream: TcpStream) -> io::Result<()> {
    let (mut from_host, mut to_client) = (upstream.try_clone()?, client.try_clone()?);
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

fn offset_device(command: Command, offset: u32) -> Command {
    match command {
        Command::AddDevice { device, kind } => Command::AddDevice {
            device: device | offset,
            kind,
        },
        Command::RemoveDevice { device } => Command::RemoveDevice {
            device: device | offset,
        },
        Command::Input {
            device,
            control,
            value,
        } => Command::Input {
            device: device | offset,
            control,
            value,
        },
        command => command,
    }
}
