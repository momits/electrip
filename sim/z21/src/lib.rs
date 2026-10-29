//! Z21 simulator, built only after the Roco specification "Z21 LAN Protokoll"
//! V1.13 (ADR 0005). It covers the commands that the scenarios of N-02 need;
//! the README lists them and the assumptions where the spec is silent.

mod loco;
#[cfg(test)]
mod tests;

use loco::{GROUPS_WITHOUT_FEEDBACK, Loco};
use std::collections::{HashMap, HashSet, VecDeque};
use std::io::{self, ErrorKind};
use std::net::{SocketAddr, UdpSocket};
use std::time::{Duration, Instant};

/// UDP port for control applications (spec 1.1).
pub const PORT: u16 = 21105;

const SERIAL_NUMBER: u32 = 210_500;
/// D_HWT_Z21_NEW, the black Z21 from 2013 (spec 2.20).
const HW_TYPE: u32 = 0x0201;
/// Firmware 1.43 in BCD, the version that spec V1.13 describes.
const FIRMWARE: u16 = 0x0143;
const XBUS_VERSION: u8 = 0x30;
/// Command station ID of the Z21 family (spec 2.3).
const CMDST_ID: u8 = 0x12;
/// capDCC | capMM | capLocoCmds (spec 2.18).
const CAPABILITIES: u8 = 0x13;

/// Clients silent for longer are dropped (spec 1.1).
const CLIENT_TIMEOUT: Duration = Duration::from_secs(60);
/// Loco subscriptions per client, oldest dropped first (spec 4).
const MAX_SUBSCRIPTIONS: usize = 16;

/// Broadcast flags (spec 2.16).
const BC_DRIVE_SWITCH: u32 = 0x0000_0001;
const BC_SYSTEM_STATE: u32 = 0x0000_0100;
const BC_ALL_LOCOS: u32 = 0x0001_0000;

/// Central state bits (spec 2.12).
const CS_EMERGENCY_STOP: u8 = 0x01;
const CS_TRACK_VOLTAGE_OFF: u8 = 0x02;

/// LAN_X_UNKNOWN_COMMAND (spec 2.11).
const UNKNOWN_COMMAND: [u8; 2] = [0x61, 0x82];

/// A UDP packet the simulator sends: receiver and payload.
pub type Packet = (SocketAddr, Vec<u8>);

/// State of the simulated Z21. It starts with track power on.
#[derive(Default)]
pub struct Z21 {
    clients: HashMap<SocketAddr, Client>,
    central_state: u8,
    locos: HashMap<u16, Loco>,
    /// Loco addresses set to MM format with LAN_SET_LOCOMODE.
    mm_locos: HashSet<u16>,
}

struct Client {
    flags: u32,
    subscriptions: VecDeque<u16>,
    last_seen: Instant,
}

impl Z21 {
    /// Handles one UDP packet from `from`, which may hold several data sets
    /// (spec 1.3), and returns the packets to send.
    pub fn handle(&mut self, from: SocketAddr, packet: &[u8], now: Instant) -> Vec<Packet> {
        self.clients
            .retain(|_, c| now.duration_since(c.last_seen) <= CLIENT_TIMEOUT);
        let mut out = Vec::new();
        let mut rest = packet;
        while let Some((header, data, tail)) = split_dataset(rest) {
            rest = tail;
            self.lan_command(from, header, data, now, &mut out);
        }
        out
    }

    fn lan_command(
        &mut self,
        from: SocketAddr,
        header: u16,
        data: &[u8],
        now: Instant,
        out: &mut Vec<Packet>,
    ) {
        if header == 0x30 {
            self.clients.remove(&from);
            return;
        }
        let client = self.clients.entry(from).or_insert_with(|| Client {
            flags: 0,
            subscriptions: VecDeque::new(),
            last_seen: now,
        });
        client.last_seen = now;
        let reply = match (header, data) {
            (0x10, []) => dataset(0x10, &SERIAL_NUMBER.to_le_bytes()),
            (0x1A, []) => {
                let firmware = u32::from(FIRMWARE).to_le_bytes();
                dataset(0x1A, &[HW_TYPE.to_le_bytes(), firmware].concat())
            }
            (0x40, x) => return self.xbus(from, x, out),
            (0x50, &[a, b, c, d]) => {
                client.flags = u32::from_le_bytes([a, b, c, d]);
                return;
            }
            (0x51, []) => dataset(0x51, &client.flags.to_le_bytes()),
            (0x60, &[h, l]) => {
                let mode = u8::from(self.is_mm(u16::from_be_bytes([h, l])));
                dataset(0x60, &[h, l, mode])
            }
            (0x61, &[h, l, mode]) => return self.set_loco_mode(u16::from_be_bytes([h, l]), mode),
            (0x85, []) => self.system_state(),
            // Everything else gets no reply, like the LAN commands without one.
            _ => return,
        };
        out.push((from, reply));
    }

    /// LAN_X commands (spec 1.2.2): X-Header, data bytes, XOR byte.
    fn xbus(&mut self, from: SocketAddr, x: &[u8], out: &mut Vec<Packet>) {
        let body = match x.split_last() {
            Some((&check, body)) if xor(body) == check => body,
            _ => return out.push((from, x_dataset(&UNKNOWN_COMMAND))),
        };
        match *body {
            [0x21, 0x21] => out.push((from, x_dataset(&[0x63, 0x21, XBUS_VERSION, CMDST_ID]))),
            [0x21, 0x24] => out.push((from, x_dataset(&[0x62, 0x22, self.central_state]))),
            [0x21, 0x80] => self.set_central_state(
                from,
                self.central_state | CS_TRACK_VOLTAGE_OFF,
                &[0x61, 0x00],
                out,
            ),
            [0x21, 0x81] => self.set_central_state(from, 0, &[0x61, 0x01], out),
            [0x80] => self.set_central_state(
                from,
                self.central_state | CS_EMERGENCY_STOP,
                &[0x81, 0x00],
                out,
            ),
            [0xF1, 0x0A] => {
                let [major, minor] = FIRMWARE.to_be_bytes();
                out.push((from, x_dataset(&[0xF3, 0x0A, major, minor])));
            }
            [0x92, h, l] => {
                let address = loco_address(h, l);
                let mm = self.is_mm(address);
                self.locos.entry(address).or_default().emergency_stop(mm);
                self.notify(address, out);
            }
            [0xE3, 0xF0, h, l] => self.subscribe(from, loco_address(h, l), out),
            [0xE4, op, h, l, value] => self.loco_command(from, loco_address(h, l), op, value, out),
            _ => out.push((from, x_dataset(&UNKNOWN_COMMAND))),
        }
    }

    /// Track power and emergency stop: the requester gets the reply, other
    /// clients get it as broadcast if they set flag 0x00000001 (spec 2.5–2.14).
    fn set_central_state(
        &mut self,
        from: SocketAddr,
        state: u8,
        message: &[u8],
        out: &mut Vec<Packet>,
    ) {
        let changed = state != self.central_state;
        self.central_state = state;
        let message = x_dataset(message);
        let system_state = self.system_state();
        for (&addr, client) in &self.clients {
            if addr == from || client.flags & BC_DRIVE_SWITCH != 0 {
                out.push((addr, message.clone()));
            }
            if changed && client.flags & BC_SYSTEM_STATE != 0 {
                out.push((addr, system_state.clone()));
            }
        }
    }

    /// LAN_X_GET_LOCO_INFO: replies with the loco state and subscribes the
    /// client to its changes (spec 4.1).
    fn subscribe(&mut self, from: SocketAddr, address: u16, out: &mut Vec<Packet>) {
        if let Some(client) = self.clients.get_mut(&from) {
            let subscriptions = &mut client.subscriptions;
            if !subscriptions.contains(&address) {
                subscriptions.push_back(address);
            }
            if subscriptions.len() > MAX_SUBSCRIPTIONS {
                subscriptions.pop_front();
            }
        }
        out.push((from, self.loco_info(address)));
    }

    /// LAN_X_SET_LOCO_DRIVE, _FUNCTION and _FUNCTION_GROUP (spec 4.2, 4.3).
    fn loco_command(
        &mut self,
        from: SocketAddr,
        address: u16,
        op: u8,
        value: u8,
        out: &mut Vec<Packet>,
    ) {
        if GROUPS_WITHOUT_FEEDBACK.contains(&op) {
            return;
        }
        let loco = self.locos.entry(address).or_default();
        let valid = match op {
            0xF8 => loco.switch_function(value),
            0x10..=0x1F => loco.drive(op, value),
            _ => loco.set_group(op, value),
        };
        if valid {
            self.notify(address, out);
        } else {
            out.push((from, x_dataset(&UNKNOWN_COMMAND)));
        }
    }

    /// Sends LAN_X_LOCO_INFO to every client that subscribed the loco, or
    /// all locos, and set flag 0x00000001 (spec 2.16, 4.4).
    fn notify(&self, address: u16, out: &mut Vec<Packet>) {
        let info = self.loco_info(address);
        for (&addr, client) in &self.clients {
            let wants_loco =
                client.flags & BC_ALL_LOCOS != 0 || client.subscriptions.contains(&address);
            if client.flags & BC_DRIVE_SWITCH != 0 && wants_loco {
                out.push((addr, info.clone()));
            }
        }
    }

    fn loco_info(&self, address: u16) -> Vec<u8> {
        let loco = self.locos.get(&address).copied().unwrap_or_default();
        x_dataset(&[&[0xEF][..], &loco.info(address, self.is_mm(address))].concat())
    }

    /// Addresses from 256 on are always DCC (spec 3.2).
    fn set_loco_mode(&mut self, address: u16, mode: u8) {
        match (address < 256, mode) {
            (true, 0) => self.mm_locos.remove(&address),
            (true, 1) => self.mm_locos.insert(address),
            _ => false,
        };
    }

    fn is_mm(&self, address: u16) -> bool {
        self.mm_locos.contains(&address)
    }

    /// LAN_SYSTEMSTATE_DATACHANGED with fixed, plausible measurements (spec 2.18).
    fn system_state(&self) -> Vec<u8> {
        let mut state = Vec::with_capacity(16);
        for value in [0i16, 0, 0, 35] {
            state.extend(value.to_le_bytes());
        }
        for value in [18_000u16, 16_000] {
            state.extend(value.to_le_bytes());
        }
        state.extend([self.central_state, 0, 0, CAPABILITIES]);
        dataset(0x84, &state)
    }
}

/// Splits the first data set off a packet: header, data and the rest.
/// Returns `None` at the end or for a malformed length.
fn split_dataset(packet: &[u8]) -> Option<(u16, &[u8], &[u8])> {
    let len = usize::from(u16::from_le_bytes([*packet.first()?, *packet.get(1)?]));
    if len < 4 || len > packet.len() {
        return None;
    }
    let header = u16::from_le_bytes([packet[2], packet[3]]);
    Some((header, &packet[4..len], &packet[len..]))
}

/// A Z21 data set: DataLen, header, data (spec 1.2.1).
fn dataset(header: u16, data: &[u8]) -> Vec<u8> {
    let len = (4 + data.len()) as u16;
    [&len.to_le_bytes()[..], &header.to_le_bytes(), data].concat()
}

/// A LAN_X data set with XOR byte (spec 1.2.2).
fn x_dataset(x: &[u8]) -> Vec<u8> {
    dataset(0x40, &[x, &[xor(x)]].concat())
}

fn xor(bytes: &[u8]) -> u8 {
    bytes.iter().fold(0, |a, b| a ^ b)
}

/// Loco address from Adr_MSB and Adr_LSB (spec 4.1).
fn loco_address(msb: u8, lsb: u8) -> u16 {
    u16::from(msb & 0x3F) << 8 | u16::from(lsb)
}

/// Runs the simulator on `socket` until a socket error occurs.
pub fn serve(socket: UdpSocket) -> io::Result<()> {
    let mut z21 = Z21::default();
    let mut buf = [0u8; 1472];
    loop {
        let (len, from) = match socket.recv_from(&mut buf) {
            Ok(received) => received,
            // Windows reports an ICMP "port unreachable" for an earlier send here.
            Err(e) if e.kind() == ErrorKind::ConnectionReset => continue,
            Err(e) => return Err(e),
        };
        for (to, bytes) in z21.handle(from, &buf[..len], Instant::now()) {
            socket.send_to(&bytes, to)?;
        }
    }
}
