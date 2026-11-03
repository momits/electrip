//! The datasets of the Z21 LAN protocol (Roco, V1.13) that the driver sends
//! and reads. Chapter numbers refer to that version.

use electrip_core::decoder::{Decoder, Protocol};
use electrip_core::station::{LocoState, StationEvent};

/// Broadcasts of driving and switching (0x00000001) and of all locos, not
/// only the subscribed ones (0x00010000), see 2.16.
const BROADCAST_FLAGS: u32 = 0x0001_0001;

/// Status bits of emergency stop, track voltage off and short circuit (2.12).
const STATUS_POWER_OFF: u8 = 0x07;

/// A dataset: length and header, both little endian, then the data (1.2).
fn dataset(header: u16, data: &[u8]) -> Vec<u8> {
    let length = (4 + data.len()) as u16;
    [&length.to_le_bytes(), &header.to_le_bytes(), data].concat()
}

/// An X-Bus dataset (header 0x40) with its checksum.
fn x_bus(bytes: &[u8]) -> Vec<u8> {
    dataset(0x40, &[bytes, &[checksum(bytes)]].concat())
}

/// The XOR of all bytes; 0 over a whole X-Bus message with its checksum.
fn checksum(bytes: &[u8]) -> u8 {
    bytes.iter().fold(0, |x, b| x ^ b)
}

/// LAN_SET_BROADCASTFLAGS (2.16).
pub fn set_broadcast_flags() -> Vec<u8> {
    dataset(0x50, &BROADCAST_FLAGS.to_le_bytes())
}

/// LAN_X_GET_STATUS (2.4); the Z21 answers with LAN_X_STATUS_CHANGED.
pub fn get_status() -> Vec<u8> {
    x_bus(&[0x21, 0x24])
}

/// LAN_LOGOFF (2.2).
pub fn logoff() -> Vec<u8> {
    dataset(0x30, &[])
}

/// LAN_X_SET_TRACK_POWER_ON and _OFF (2.5, 2.6).
pub fn set_power(on: bool) -> Vec<u8> {
    x_bus(&[0x21, if on { 0x81 } else { 0x80 }])
}

/// LAN_SET_LOCOMODE (3.2): DCC or Motorola for an address.
pub fn set_loco_mode(decoder: &Decoder) -> Vec<u8> {
    let motorola = matches!(
        decoder.protocol(),
        Protocol::Motorola1 | Protocol::Motorola2
    );
    let [msb, lsb] = decoder.address().to_be_bytes();
    dataset(0x61, &[msb, lsb, u8::from(motorola)])
}

/// LAN_X_SET_LOCO_DRIVE (4.2); the speed value 1 is the emergency stop.
pub fn set_loco_drive(decoder: &Decoder, forward: bool, step: u8, emergency: bool) -> Vec<u8> {
    let steps = decoder.speed_steps();
    let speed = if emergency {
        1
    } else {
        speed_value(steps, step)
    };
    let format = match steps {
        14 => 0x10,
        28 => 0x12,
        _ => 0x13,
    };
    let [msb, lsb] = address_bytes(decoder.address());
    x_bus(&[0xE4, format, msb, lsb, u8::from(forward) << 7 | speed])
}

/// LAN_X_SET_LOCO_FUNCTION (4.3): switches function `number` on or off.
pub fn set_loco_function(address: u16, number: u8, on: bool) -> Vec<u8> {
    let [msb, lsb] = address_bytes(address);
    x_bus(&[0xE4, 0xF8, msb, lsb, u8::from(on) << 6 | number])
}

/// From address 128 on, Adr_MSB carries the bits 0xC0 (4.1).
fn address_bytes(address: u16) -> [u8; 2] {
    let [msb, lsb] = address.to_be_bytes();
    [if address >= 128 { msb | 0xC0 } else { msb }, lsb]
}

/// The speed value of a step: 0 stops, 1 is the emergency stop. With 28
/// steps the lowest bit of the value moves to bit 4 (4.2).
fn speed_value(steps: u8, step: u8) -> u8 {
    match (steps, step) {
        (_, 0) => 0,
        (14, _) => step.min(14) + 1,
        (28, _) => {
            let value = step.min(28) + 3;
            (value & 1) << 4 | value >> 1
        }
        _ => step.min(126) + 1,
    }
}

/// The step of a speed value in the format KKK of LAN_X_LOCO_INFO (4.4).
fn speed_step(format: u8, value: u8) -> u8 {
    let value = match format {
        2 => ((value & 0x0F) << 1 | value >> 4 & 1).saturating_sub(2),
        _ => value,
    };
    value.saturating_sub(1)
}

/// The events in a UDP packet, which may hold several datasets (1.3).
pub fn parse(packet: &[u8]) -> Vec<StationEvent> {
    let mut events = Vec::new();
    let mut rest = packet;
    while let [l0, l1, h0, h1, ..] = *rest {
        let length = usize::from(u16::from_le_bytes([l0, l1]));
        if length < 4 || length > rest.len() {
            break;
        }
        if u16::from_le_bytes([h0, h1]) == 0x40 {
            events.extend(parse_x_bus(&rest[4..length]));
        }
        rest = &rest[length..];
    }
    events
}

fn parse_x_bus(bytes: &[u8]) -> Option<StationEvent> {
    if checksum(bytes) != 0 {
        return None;
    }
    match *bytes {
        // LAN_X_BC_TRACK_POWER_OFF, _ON, _SHORT_CIRCUIT (2.7–2.9).
        [0x61, 0x00, _] | [0x61, 0x08, _] => Some(StationEvent::Power(false)),
        [0x61, 0x01, _] => Some(StationEvent::Power(true)),
        // LAN_X_BC_STOPPED (2.14).
        [0x81, 0x00, _] => Some(StationEvent::Power(false)),
        // LAN_X_STATUS_CHANGED (2.12).
        [0x62, 0x22, status, _] => Some(StationEvent::Power(status & STATUS_POWER_OFF == 0)),
        // LAN_X_LOCO_INFO (4.4).
        [0xEF, msb, lsb, format, speed, db4, db5, db6, db7, ..] => {
            let functions = u32::from(db4 >> 4 & 1)
                | u32::from(db4 & 0x0F) << 1
                | u32::from(db5) << 5
                | u32::from(db6) << 13
                | u32::from(db7) << 21;
            let state = LocoState {
                forward: speed & 0x80 != 0,
                step: speed_step(format & 0x07, speed & 0x7F),
                functions,
            };
            let address = u16::from_be_bytes([msb & 0x3F, lsb]);
            Some(StationEvent::Loco { address, state })
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests;
