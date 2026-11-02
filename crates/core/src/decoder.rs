//! Decoder settings of a loco: protocol, address and speed steps (B-06).

use serde::{Deserialize, Serialize};
use std::fmt;

/// Decoder protocol, kept neutral; each command station driver translates it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Protocol {
    Motorola1,
    Motorola2,
    DccShort,
    DccLong,
}

impl Protocol {
    pub fn max_address(self) -> u16 {
        match self {
            Protocol::Motorola1 => 80,
            Protocol::Motorola2 => 255,
            Protocol::DccShort => 127,
            Protocol::DccLong => 10239,
        }
    }

    /// Allowed speed step counts, ascending.
    pub fn speed_step_options(self) -> &'static [u8] {
        match self {
            Protocol::Motorola1 => &[14],
            Protocol::Motorola2 => &[14, 28],
            Protocol::DccShort | Protocol::DccLong => &[14, 28, 128],
        }
    }

    fn max_speed_steps(self) -> u8 {
        self.speed_step_options().last().copied().unwrap_or(14)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DecoderError {
    AddressOutOfRange { max: u16 },
    SpeedStepsNotSupported { options: &'static [u8] },
}

impl fmt::Display for DecoderError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            DecoderError::AddressOutOfRange { max } => {
                write!(f, "the address must be between 1 and {max}")
            }
            DecoderError::SpeedStepsNotSupported { options } => {
                write!(f, "the protocol allows only these speed steps: {options:?}")
            }
        }
    }
}

/// A valid combination of protocol, address and speed steps.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Decoder {
    protocol: Protocol,
    address: u16,
    speed_steps: u8,
}

impl Decoder {
    pub fn new(protocol: Protocol, address: u16, speed_steps: u8) -> Result<Self, DecoderError> {
        let mut decoder = Decoder {
            protocol,
            address: 1,
            speed_steps: protocol.max_speed_steps(),
        };
        decoder.set_address(address)?;
        decoder.set_speed_steps(speed_steps)?;
        Ok(decoder)
    }

    pub fn protocol(&self) -> Protocol {
        self.protocol
    }

    pub fn address(&self) -> u16 {
        self.address
    }

    pub fn speed_steps(&self) -> u8 {
        self.speed_steps
    }

    pub fn set_address(&mut self, address: u16) -> Result<(), DecoderError> {
        let max = self.protocol.max_address();
        if !(1..=max).contains(&address) {
            return Err(DecoderError::AddressOutOfRange { max });
        }
        self.address = address;
        Ok(())
    }

    pub fn set_speed_steps(&mut self, speed_steps: u8) -> Result<(), DecoderError> {
        let options = self.protocol.speed_step_options();
        if !options.contains(&speed_steps) {
            return Err(DecoderError::SpeedStepsNotSupported { options });
        }
        self.speed_steps = speed_steps;
        Ok(())
    }

    /// Switches the protocol like Electrip 1: the address is capped at the new
    /// maximum and the speed steps become the highest the protocol allows.
    pub fn set_protocol(&mut self, protocol: Protocol) {
        self.protocol = protocol;
        self.address = self.address.min(protocol.max_address());
        self.speed_steps = protocol.max_speed_steps();
    }
}

#[cfg(test)]
mod tests;
