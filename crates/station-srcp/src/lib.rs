//! Driver for SRCP 0.8 servers such as srcpd (N-02). A COMMAND session sends
//! the commands, an INFO session in its own thread reports every change.

use electrip_core::decoder::{Decoder, Protocol};
use electrip_core::station::{CommandStation, LocoState, MAX_FUNCTION, StationError, StationEvent};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::net::{Shutdown, TcpStream, ToSocketAddrs};
use std::sync::mpsc::{Receiver, Sender, channel};
use std::thread;
use std::time::Duration;

pub const DEFAULT_PORT: u16 = 4303;

const TIMEOUT: Duration = Duration::from_secs(3);

pub struct SrcpStation {
    command: BufReader<TcpStream>,
    info: TcpStream,
    bus: u16,
    /// The decoder of the last INIT in this session, by address.
    initialized: HashMap<u16, Decoder>,
    events: Receiver<StationEvent>,
}

impl SrcpStation {
    pub fn connect(host: &str, port: u16, bus: u16) -> Result<Self, StationError> {
        let mut command = open(host, port, "COMMAND")?;
        // INIT POWER as in Electrip 1; it also tells whether the bus exists.
        request(&mut command, &format!("INIT {bus} POWER"))
            .map_err(|e| StationError(format!("the SRCP server has no bus {bus}: {e}")))?;
        let info = open(host, port, "INFO")?;
        let (sender, events) = channel();
        let reader = info.get_ref().try_clone().map_err(io_error)?;
        reader.set_read_timeout(None).map_err(io_error)?;
        thread::spawn(move || read_info(BufReader::new(reader), bus, sender));
        Ok(SrcpStation {
            command,
            info: info.into_inner(),
            bus,
            initialized: HashMap::new(),
            events,
        })
    }

    /// Sends `SET <bus> GL` with drive mode 0 (back), 1 (forward) or 2
    /// (emergency stop) and all functions, since srcpd clears missing ones.
    fn send_loco(
        &mut self,
        decoder: &Decoder,
        mode: u8,
        state: &LocoState,
    ) -> Result<(), StationError> {
        let (bus, address, steps) = (self.bus, decoder.address(), decoder.speed_steps());
        if self.initialized.get(&address) != Some(decoder) {
            let (protocol, functions) = srcp_protocol(decoder.protocol());
            let init = format!("INIT {bus} GL {address} {protocol} {steps} {functions}");
            request(&mut self.command, &init)?;
            self.initialized.insert(address, *decoder);
        }
        let functions: Vec<&str> = (0..=MAX_FUNCTION)
            .map(|n| if state.function(n) { "1" } else { "0" })
            .collect();
        let set = format!(
            "SET {bus} GL {address} {mode} {} {steps} {}",
            state.step,
            functions.join(" ")
        );
        request(&mut self.command, &set)
    }
}

impl CommandStation for SrcpStation {
    fn set_power(&mut self, on: bool) -> Result<(), StationError> {
        let state = if on { "ON" } else { "OFF" };
        request(
            &mut self.command,
            &format!("SET {} POWER {state}", self.bus),
        )
    }

    fn set_loco(&mut self, decoder: &Decoder, state: &LocoState) -> Result<(), StationError> {
        self.send_loco(decoder, u8::from(state.forward), state)
    }

    fn emergency_stop(&mut self, decoder: &Decoder, state: &LocoState) -> Result<(), StationError> {
        self.send_loco(decoder, 2, state)
    }

    fn events(&mut self) -> Vec<StationEvent> {
        self.events.try_iter().collect()
    }
}

impl Drop for SrcpStation {
    fn drop(&mut self) {
        let _ = writeln!(self.command.get_mut(), "TERM 0 SESSION");
        let _ = self.info.shutdown(Shutdown::Both);
    }
}

/// Protocol and function count (F0 included) for `INIT GL`, as Electrip 1.
fn srcp_protocol(protocol: Protocol) -> (&'static str, u8) {
    match protocol {
        Protocol::Motorola1 => ("M 1", 1),
        Protocol::Motorola2 => ("M 2", 5),
        Protocol::DccShort => ("N 1", MAX_FUNCTION + 1),
        Protocol::DccLong => ("N 2", MAX_FUNCTION + 1),
    }
}

/// Connects and starts a session in `mode` (COMMAND or INFO).
fn open(host: &str, port: u16, mode: &str) -> Result<BufReader<TcpStream>, StationError> {
    let unreachable =
        |e: String| StationError(format!("cannot reach the SRCP server {host}:{port}: {e}"));
    let addr = (host, port)
        .to_socket_addrs()
        .map_err(|e| unreachable(e.to_string()))?
        .next()
        .ok_or_else(|| unreachable("unknown host".into()))?;
    let stream =
        TcpStream::connect_timeout(&addr, TIMEOUT).map_err(|e| unreachable(e.to_string()))?;
    stream.set_read_timeout(Some(TIMEOUT)).map_err(io_error)?;
    let mut session = BufReader::new(stream);
    let greeting = read_line(&mut session)?;
    if !greeting.contains("SRCP 0.8") {
        return Err(StationError(format!(
            "{host}:{port} is no SRCP 0.8 server: '{greeting}'"
        )));
    }
    request(&mut session, &format!("SET CONNECTIONMODE SRCP {mode}"))?;
    request(&mut session, "GO")?;
    Ok(session)
}

/// Sends one command and expects a reply with a 2xx code.
fn request(session: &mut BufReader<TcpStream>, command: &str) -> Result<(), StationError> {
    writeln!(session.get_mut(), "{command}").map_err(io_error)?;
    let reply = read_line(session)?;
    match reply.split_whitespace().nth(1) {
        Some(code) if code.starts_with('2') => Ok(()),
        _ => Err(StationError(format!(
            "the SRCP server rejected '{command}': '{reply}'"
        ))),
    }
}

fn read_line(session: &mut BufReader<TcpStream>) -> Result<String, StationError> {
    let mut line = String::new();
    match session.read_line(&mut line) {
        Ok(0) => Err(StationError("the SRCP server closed the connection".into())),
        Ok(_) => Ok(line.trim_end().to_string()),
        Err(e) => Err(io_error(e)),
    }
}

/// Forwards the changes on `bus` until the connection ends.
fn read_info(mut session: BufReader<TcpStream>, bus: u16, events: Sender<StationEvent>) {
    let mut directions = HashMap::new();
    while let Ok(line) = read_line(&mut session) {
        if let Some(event) = parse_info(&line, bus, &mut directions)
            && events.send(event).is_err()
        {
            return;
        }
    }
    let _ = events.send(StationEvent::Disconnected);
}

/// Parses `<time> 100 INFO <bus> POWER ON|OFF` and
/// `<time> 100 INFO <bus> GL <address> <mode> <step> <steps> <f0> …`.
/// Drive mode 2 is an emergency stop; the loco keeps the direction from
/// `directions`, the last one reported per address.
fn parse_info(line: &str, bus: u16, directions: &mut HashMap<u16, bool>) -> Option<StationEvent> {
    let words: Vec<&str> = line.split_whitespace().collect();
    let [_, "100", "INFO", line_bus, device, rest @ ..] = words.as_slice() else {
        return None;
    };
    if line_bus.parse() != Ok(bus) {
        return None;
    }
    match (*device, rest) {
        ("POWER", [state]) => Some(StationEvent::Power(*state == "ON")),
        ("GL", [address, mode, step, _, functions @ ..]) => {
            let functions = functions
                .iter()
                .take(usize::from(MAX_FUNCTION) + 1)
                .enumerate()
                .filter(|(_, f)| **f == "1")
                .fold(0, |bits, (n, _)| bits | 1 << n);
            let address = address.parse().ok()?;
            let forward = directions.entry(address).or_insert(true);
            if *mode != "2" {
                *forward = *mode == "1";
            }
            let state = LocoState {
                forward: *forward,
                step: step.parse().ok()?,
                functions,
            };
            Some(StationEvent::Loco { address, state })
        }
        _ => None,
    }
}

fn io_error(e: std::io::Error) -> StationError {
    StationError(format!("connection to the SRCP server failed: {e}"))
}

#[cfg(test)]
mod tests;
