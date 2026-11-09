//! Driver for the Roco Z21 over UDP (N-02), built from the specification
//! alone and checked against it; experimental in Electrip 2.0.
//! The host polls `events` often, so the driver needs no thread.

mod telegram;

use electrip_core::decoder::Decoder;
use electrip_core::station::{CommandStation, LocoState, MAX_FUNCTION, StationError, StationEvent};
use std::collections::HashMap;
use std::io::ErrorKind;
use std::net::{ToSocketAddrs, UdpSocket};
use std::time::{Duration, Instant};

pub const DEFAULT_PORT: u16 = 21105;

const TIMEOUT: Duration = Duration::from_secs(3);

/// The Z21 logs a client off after a minute without a message (1.1).
const KEEPALIVE: Duration = Duration::from_secs(20);

/// Without an answer to three keepalives the Z21 counts as gone.
const SILENCE: Duration = Duration::from_secs(70);

pub struct Z21Station {
    socket: UdpSocket,
    /// The decoder and state the Z21 last had, by address.
    known: HashMap<u16, (Decoder, LocoState)>,
    /// Events read while connecting.
    pending: Vec<StationEvent>,
    last_sent: Instant,
    last_heard: Instant,
}

impl Z21Station {
    /// Logs on and waits for the status, which tells the track power.
    pub fn connect(host: &str, port: u16) -> Result<Self, StationError> {
        let unreachable =
            |e: String| StationError(format!("cannot reach the Z21 {host}:{port}: {e}"));
        let addr = (host, port)
            .to_socket_addrs()
            .map_err(|e| unreachable(e.to_string()))?
            .next()
            .ok_or_else(|| unreachable("unknown host".into()))?;
        let local = if addr.is_ipv4() {
            "0.0.0.0:0"
        } else {
            "[::]:0"
        };
        let socket = UdpSocket::bind(local).map_err(|e| unreachable(e.to_string()))?;
        socket
            .connect(addr)
            .map_err(|e| unreachable(e.to_string()))?;
        socket.set_read_timeout(Some(TIMEOUT)).map_err(io_error)?;
        let mut station = Z21Station {
            socket,
            known: HashMap::new(),
            pending: Vec::new(),
            last_sent: Instant::now(),
            last_heard: Instant::now(),
        };
        station.send(&[telegram::set_broadcast_flags(), telegram::get_status()].concat())?;
        let no_answer = |e| StationError(format!("no Z21 answers on {host}:{port}: {e}"));
        while !station
            .pending
            .iter()
            .any(|e| matches!(e, StationEvent::Power(_)))
        {
            let events = station.receive().map_err(no_answer)?;
            station.pending.extend(events);
        }
        station.socket.set_nonblocking(true).map_err(io_error)?;
        Ok(station)
    }

    fn send(&mut self, packet: &[u8]) -> Result<(), StationError> {
        self.socket.send(packet).map_err(io_error)?;
        self.last_sent = Instant::now();
        Ok(())
    }

    /// Reads one packet and notes what the Z21 now has.
    fn receive(&mut self) -> std::io::Result<Vec<StationEvent>> {
        let mut buffer = [0; 1500];
        let length = self.socket.recv(&mut buffer)?;
        self.last_heard = Instant::now();
        let mut events = telegram::parse(&buffer[..length]);
        for event in &mut events {
            if let StationEvent::Loco { address, state } = event
                && let Some((decoder, known)) = self.known.get_mut(address)
            {
                // The step the host sent, unless the Z21 has another.
                if telegram::z21_step(decoder, known.step) != state.step {
                    known.step = telegram::host_step(decoder, state.step);
                }
                state.step = known.step;
                *known = *state;
            }
        }
        Ok(events)
    }

    /// Sends what differs from the state the Z21 last had: the loco mode,
    /// drive and each function on its own, since every command makes the
    /// Z21 report the loco to all clients.
    fn send_loco(
        &mut self,
        decoder: &Decoder,
        state: &LocoState,
        emergency: bool,
    ) -> Result<(), StationError> {
        let address = decoder.address();
        let known = self.known.get(&address).copied();
        let same_decoder = known.map(|(d, _)| d) == Some(*decoder);
        let mut packet = Vec::new();
        if known.map(|(d, _)| d.protocol()) != Some(decoder.protocol()) {
            packet.extend(telegram::set_loco_mode(decoder));
        }
        let step = if emergency { 0 } else { state.step };
        let drive = known.map(|(_, s)| (s.forward, s.step));
        if emergency || !same_decoder || drive != Some((state.forward, step)) {
            packet.extend(telegram::set_loco_drive(
                decoder,
                state.forward,
                step,
                emergency,
            ));
        }
        for number in 0..=MAX_FUNCTION {
            let on = state.function(number);
            if known.map(|(_, s)| s.function(number)) != Some(on) {
                packet.extend(telegram::set_loco_function(address, number, on));
            }
        }
        if !packet.is_empty() {
            self.send(&packet)?;
        }
        self.known
            .insert(address, (*decoder, LocoState { step, ..*state }));
        Ok(())
    }
}

impl CommandStation for Z21Station {
    fn set_power(&mut self, on: bool) -> Result<(), StationError> {
        self.send(&telegram::set_power(on))
    }

    fn set_loco(&mut self, decoder: &Decoder, state: &LocoState) -> Result<(), StationError> {
        self.send_loco(decoder, state, false)
    }

    fn emergency_stop(&mut self, decoder: &Decoder, state: &LocoState) -> Result<(), StationError> {
        self.send_loco(decoder, state, true)
    }

    fn events(&mut self) -> Vec<StationEvent> {
        let mut events = std::mem::take(&mut self.pending);
        loop {
            match self.receive() {
                Ok(received) => events.extend(received),
                Err(e) if e.kind() == ErrorKind::WouldBlock => break,
                Err(_) => return disconnected(events),
            }
        }
        if self.last_heard.elapsed() > SILENCE {
            return disconnected(events);
        }
        if self.last_sent.elapsed() > KEEPALIVE && self.send(&telegram::get_status()).is_err() {
            return disconnected(events);
        }
        events
    }
}

impl Drop for Z21Station {
    fn drop(&mut self) {
        let _ = self.socket.send(&telegram::logoff());
    }
}

fn disconnected(mut events: Vec<StationEvent>) -> Vec<StationEvent> {
    events.push(StationEvent::Disconnected);
    events
}

fn io_error(e: std::io::Error) -> StationError {
    StationError(format!("connection to the Z21 failed: {e}"))
}

#[cfg(test)]
mod tests;
