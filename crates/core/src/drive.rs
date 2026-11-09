//! Driving a loco with a gamepad axis (B-10). The deflection of the axis sets
//! the acceleration, not the speed: full deflection forward reaches Vmax from
//! standstill in the acceleration duration, full deflection back stops from
//! Vmax in the braking duration, as in Electrip 1.

use crate::loco::Loco;
use serde::Serialize;

/// Axis deflections up to this are ignored; the default of Electrip 1.
pub const DEAD_ZONE: f64 = 0.06;

/// The deflection of an axis, clamped to -1 to 1; within the dead zone it
/// is 0, so the speed stays.
pub fn deflection(value: f64, dead_zone: f64) -> f64 {
    if value.abs() <= dead_zone {
        0.0
    } else {
        value.clamp(-1.0, 1.0)
    }
}

/// Speed in km/h and direction of a loco.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct Motion {
    speed: f64,
    forward: bool,
}

impl Default for Motion {
    fn default() -> Self {
        Motion {
            speed: 0.0,
            forward: true,
        }
    }
}

impl Motion {
    pub(crate) fn new(speed: f64, forward: bool) -> Self {
        Motion { speed, forward }
    }

    pub fn speed(&self) -> f64 {
        self.speed
    }

    pub fn forward(&self) -> bool {
        self.forward
    }

    /// Changes the speed for `seconds` with the axis at `deflection` (-1 full
    /// back to 1 full forward), between standstill and Vmax.
    pub fn accelerate(&mut self, loco: &Loco, deflection: f64, seconds: f64) {
        if deflection == 0.0 {
            return;
        }
        let duration = if deflection > 0.0 {
            loco.accel_duration()
        } else {
            loco.brake_duration()
        };
        let change = deflection * loco.max_speed() / duration * seconds;
        self.speed = (self.speed + change).clamp(0.0, loco.max_speed());
    }

    /// The direction switch: stops at once, then changes the direction.
    pub fn reverse(&mut self) {
        self.stop();
        self.forward = !self.forward;
    }

    pub fn stop(&mut self) {
        self.speed = 0.0;
    }
}

#[cfg(test)]
mod tests;
