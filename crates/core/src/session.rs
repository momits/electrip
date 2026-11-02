//! The state of a session and the commands that change it (ADR 0002). UI,
//! gamepads, the control channel and tests change the state only through
//! [`Session::apply`].

use crate::decoder::{Decoder, Protocol};
use crate::loco::{Loco, LocoError};
use serde::{Deserialize, Serialize};
use std::fmt;

/// A user action. Locos are addressed by their id in the session.
#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(tag = "command", rename_all = "snake_case")]
pub enum Command {
    /// Adds a loco with the defaults of Electrip 1.
    AddLoco,
    RenameLoco {
        loco: u32,
        name: String,
    },
    RemoveLoco {
        loco: u32,
    },
    /// Moves a loco to `position` (from 0) in the loco list.
    MoveLoco {
        loco: u32,
        position: usize,
    },
    SetAddress {
        loco: u32,
        address: u16,
    },
    SetProtocol {
        loco: u32,
        protocol: Protocol,
        #[serde(default)]
        confirmed: bool,
    },
    SetSpeedSteps {
        loco: u32,
        speed_steps: u8,
        #[serde(default)]
        confirmed: bool,
    },
    SetMaxSpeed {
        loco: u32,
        max_speed: f64,
        #[serde(default)]
        confirmed: bool,
    },
    SetAccelDuration {
        loco: u32,
        seconds: f64,
    },
    SetBrakeDuration {
        loco: u32,
        seconds: f64,
    },
    /// Volume from 0 (silent) to 1 (full).
    SetVolume {
        loco: u32,
        volume: f64,
    },
    AddCurvePoint {
        loco: u32,
        speed: f64,
        step: f64,
    },
    RemoveCurvePoint {
        loco: u32,
        point: usize,
    },
    MoveCurvePoint {
        loco: u32,
        point: usize,
        speed: f64,
        step: f64,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub enum CommandError {
    UnknownLoco(u32),
    PositionOutOfRange(usize),
    Loco(LocoError),
}

impl From<LocoError> for CommandError {
    fn from(error: LocoError) -> Self {
        CommandError::Loco(error)
    }
}

impl fmt::Display for CommandError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            CommandError::UnknownLoco(id) => write!(f, "there is no loco with id {id}"),
            CommandError::PositionOutOfRange(position) => {
                write!(f, "there is no position {position} in the loco list")
            }
            CommandError::Loco(error) => error.fmt(f),
        }
    }
}

/// Connection to the command station; no driver exists yet.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Station {
    #[default]
    Disconnected,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LocoEntry {
    pub id: u32,
    #[serde(flatten)]
    pub loco: Loco,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Session {
    locos: Vec<LocoEntry>,
    station: Station,
    /// Ids are never reused, so a command for a removed loco cannot hit a
    /// new one.
    #[serde(skip)]
    last_id: u32,
}

impl Session {
    pub fn locos(&self) -> &[LocoEntry] {
        &self.locos
    }

    /// Executes a command; on an error the session stays unchanged.
    pub fn apply(&mut self, command: Command) -> Result<(), CommandError> {
        match command {
            Command::AddLoco => self.add_loco()?,
            Command::RenameLoco { loco, name } => self.loco(loco)?.set_name(name),
            Command::RemoveLoco { loco } => {
                self.locos.remove(self.index(loco)?);
            }
            Command::MoveLoco { loco, position } => self.move_loco(loco, position)?,
            Command::SetAddress { loco, address } => self.loco(loco)?.set_address(address)?,
            Command::SetProtocol {
                loco,
                protocol,
                confirmed,
            } => self.loco(loco)?.set_protocol(protocol, confirmed)?,
            Command::SetSpeedSteps {
                loco,
                speed_steps,
                confirmed,
            } => self.loco(loco)?.set_speed_steps(speed_steps, confirmed)?,
            Command::SetMaxSpeed {
                loco,
                max_speed,
                confirmed,
            } => self.loco(loco)?.set_max_speed(max_speed, confirmed)?,
            Command::SetAccelDuration { loco, seconds } => {
                self.loco(loco)?.set_accel_duration(seconds)?
            }
            Command::SetBrakeDuration { loco, seconds } => {
                self.loco(loco)?.set_brake_duration(seconds)?
            }
            Command::SetVolume { loco, volume } => self.loco(loco)?.set_volume(volume)?,
            Command::AddCurvePoint { loco, speed, step } => {
                self.loco(loco)?.speed_curve_mut().add_point(speed, step)
            }
            Command::RemoveCurvePoint { loco, point } => {
                self.loco(loco)?.speed_curve_mut().remove_point(point)
            }
            Command::MoveCurvePoint {
                loco,
                point,
                speed,
                step,
            } => self
                .loco(loco)?
                .speed_curve_mut()
                .move_point(point, speed, step),
        }
        Ok(())
    }

    /// Defaults of Electrip 1: DCC short, address 1, 128 steps, 100 km/h;
    /// [`Loco::new`] adds the rest.
    fn add_loco(&mut self) -> Result<(), LocoError> {
        let loco = Loco::new(Decoder::new(Protocol::DccShort, 1, 128)?, 100.0)?;
        self.last_id += 1;
        self.locos.push(LocoEntry {
            id: self.last_id,
            loco,
        });
        Ok(())
    }

    fn move_loco(&mut self, id: u32, position: usize) -> Result<(), CommandError> {
        if position >= self.locos.len() {
            return Err(CommandError::PositionOutOfRange(position));
        }
        let entry = self.locos.remove(self.index(id)?);
        self.locos.insert(position, entry);
        Ok(())
    }

    fn index(&self, id: u32) -> Result<usize, CommandError> {
        self.locos
            .iter()
            .position(|e| e.id == id)
            .ok_or(CommandError::UnknownLoco(id))
    }

    fn loco(&mut self, id: u32) -> Result<&mut Loco, CommandError> {
        let index = self.index(id)?;
        Ok(&mut self.locos[index].loco)
    }
}

#[cfg(test)]
mod tests;
