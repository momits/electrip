//! The interface to a command station (N-02). Each driver translates it into
//! its protocol; the session host holds the loco state and sends it whole.

use crate::decoder::Decoder;
use std::fmt;

/// Highest loco function a driver must switch (F0–F28).
pub const MAX_FUNCTION: u8 = 28;

/// What a loco does: direction, speed step (0 stops) and functions.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct LocoState {
    pub forward: bool,
    pub step: u8,
    /// Bit n is function Fn.
    pub functions: u32,
}

impl LocoState {
    pub fn function(&self, number: u8) -> bool {
        self.functions & (1 << number) != 0
    }

    pub fn set_function(&mut self, number: u8, on: bool) {
        if on {
            self.functions |= 1 << number;
        } else {
            self.functions &= !(1 << number);
        }
    }
}

/// A change at the command station, also when another program made it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StationEvent {
    Power(bool),
    Loco {
        address: u16,
        state: LocoState,
    },
    /// The connection broke; the driver is useless from now on.
    Disconnected,
}

/// An error with a message the user understands.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StationError(pub String);

impl fmt::Display for StationError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        f.write_str(&self.0)
    }
}

pub trait CommandStation {
    /// Switches the track power; off is the emergency stop of the layout.
    fn set_power(&mut self, on: bool) -> Result<(), StationError>;

    fn set_loco(&mut self, decoder: &Decoder, state: &LocoState) -> Result<(), StationError>;

    /// Stops the loco at once; direction and functions stay as in `state`.
    fn emergency_stop(&mut self, decoder: &Decoder, state: &LocoState) -> Result<(), StationError>;

    /// The events since the last call, oldest first.
    fn events(&mut self) -> Vec<StationEvent>;
}

#[cfg(test)]
mod tests;
