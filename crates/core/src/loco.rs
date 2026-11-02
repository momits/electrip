//! A loco with its decoder, maximum speed and speed curve. Changing the
//! maximum speed, the speed steps or the protocol changes the axes of the
//! curve and resets it, which needs a confirmation (B-09).

use crate::decoder::{Decoder, DecoderError, Protocol};
use crate::speed_curve::SpeedCurve;

/// Allowed maximum speed in km/h, as in Electrip 1.
pub const MAX_SPEED_RANGE: std::ops::RangeInclusive<f64> = 1.0..=999.0;

#[derive(Debug, Clone, PartialEq)]
pub enum LocoError {
    Decoder(DecoderError),
    MaxSpeedOutOfRange,
    /// The change would reset the speed curve and was not confirmed; nothing
    /// changed.
    ResetNotConfirmed,
}

impl From<DecoderError> for LocoError {
    fn from(error: DecoderError) -> Self {
        LocoError::Decoder(error)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Loco {
    decoder: Decoder,
    max_speed: f64,
    speed_curve: SpeedCurve,
}

impl Loco {
    /// A loco with a straight speed curve from standstill to Vmax.
    pub fn new(decoder: Decoder, max_speed: f64) -> Result<Self, LocoError> {
        check_max_speed(max_speed)?;
        Ok(Loco {
            decoder,
            max_speed,
            speed_curve: SpeedCurve::straight(max_speed, decoder.speed_steps().into()),
        })
    }

    pub fn decoder(&self) -> &Decoder {
        &self.decoder
    }

    pub fn max_speed(&self) -> f64 {
        self.max_speed
    }

    pub fn speed_curve(&self) -> &SpeedCurve {
        &self.speed_curve
    }

    pub fn set_address(&mut self, address: u16) -> Result<(), LocoError> {
        Ok(self.decoder.set_address(address)?)
    }

    pub fn set_max_speed(&mut self, max_speed: f64, confirmed: bool) -> Result<(), LocoError> {
        check_max_speed(max_speed)?;
        self.change_axes(confirmed, |loco| {
            loco.max_speed = max_speed;
            Ok(())
        })
    }

    pub fn set_speed_steps(&mut self, speed_steps: u8, confirmed: bool) -> Result<(), LocoError> {
        self.change_axes(confirmed, |loco| {
            Ok(loco.decoder.set_speed_steps(speed_steps)?)
        })
    }

    /// Switches the protocol like [`Decoder::set_protocol`]; this always sets
    /// the highest speed steps and so resets the curve.
    pub fn set_protocol(&mut self, protocol: Protocol, confirmed: bool) -> Result<(), LocoError> {
        self.change_axes(confirmed, |loco| {
            loco.decoder.set_protocol(protocol);
            Ok(())
        })
    }

    /// Applies a change of the curve's axes and resets the curve. Leaves the
    /// loco unchanged if nothing changes, the change fails or it is not
    /// confirmed.
    fn change_axes(
        &mut self,
        confirmed: bool,
        change: impl FnOnce(&mut Loco) -> Result<(), LocoError>,
    ) -> Result<(), LocoError> {
        let mut loco = self.clone();
        change(&mut loco)?;
        if loco == *self {
            return Ok(());
        }
        if !confirmed {
            return Err(LocoError::ResetNotConfirmed);
        }
        loco.speed_curve = SpeedCurve::straight(loco.max_speed, loco.decoder.speed_steps().into());
        *self = loco;
        Ok(())
    }
}

fn check_max_speed(max_speed: f64) -> Result<(), LocoError> {
    if MAX_SPEED_RANGE.contains(&max_speed) {
        Ok(())
    } else {
        Err(LocoError::MaxSpeedOutOfRange)
    }
}

#[cfg(test)]
mod tests;
