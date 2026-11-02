//! The state of a session and the commands that change it (ADR 0002). UI,
//! gamepads, the control channel and tests change the state only through
//! [`Host::apply`](crate::host::Host::apply).

use crate::decoder::{Decoder, Protocol};
use crate::drive::{DEAD_ZONE, Motion};
use crate::electrip1::{self, ImportError};
use crate::loco::{Loco, LocoError};
use crate::station::{LocoState, StationError};
use serde::{Deserialize, Serialize};
use std::fmt;
use std::path::{Path, PathBuf};

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
    /// Deflection of the drive axis from -1 (full back) to 1 (full forward);
    /// the host accelerates the loco with it until the next one (B-10).
    SetAxis {
        loco: u32,
        deflection: f64,
    },
    /// The direction switch: stops the loco and changes its direction.
    Reverse {
        loco: u32,
    },
    /// Where the SRCP server is; only while disconnected.
    SetServer {
        host: String,
        port: u16,
        bus: u16,
    },
    /// Connects to the server; the host also replaces an open connection.
    Connect,
    Disconnect,
    /// Replaces the locos and the server with those of a configuration
    /// file of Electrip 1 on the host; only while disconnected (B-21).
    ImportElectrip1 {
        path: PathBuf,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub enum CommandError {
    UnknownLoco(u32),
    PositionOutOfRange(usize),
    Loco(LocoError),
    Connected,
    Station(StationError),
    Import(ImportError),
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
            CommandError::Connected => f.write_str("disconnect from the command station first"),
            CommandError::Station(error) => error.fmt(f),
            CommandError::Import(error) => error.fmt(f),
        }
    }
}

/// The SRCP server and whether the host is connected to it (B-01). Read
/// from a file, missing values get the defaults and it is disconnected.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct Station {
    pub host: String,
    pub port: u16,
    pub bus: u16,
    #[serde(skip_deserializing)]
    pub connected: bool,
}

/// Defaults of Electrip 1.
impl Default for Station {
    fn default() -> Self {
        Station {
            host: "localhost".into(),
            port: 4303,
            bus: 1,
            connected: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LocoEntry {
    pub id: u32,
    #[serde(flatten)]
    pub loco: Loco,
    #[serde(flatten)]
    pub motion: Motion,
    #[serde(skip)]
    axis: f64,
}

impl LocoEntry {
    /// What the command station gets: the speed step from the speed curve,
    /// cut off like Electrip 1. Functions follow with B-07.
    pub fn station_state(&self) -> LocoState {
        let curve = self.loco.speed_curve();
        let step = curve.step_at(self.motion.speed()).unwrap_or(0.0);
        LocoState {
            forward: self.motion.forward(),
            step: step as u8,
            functions: 0,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Session {
    locos: Vec<LocoEntry>,
    station: Station,
    /// Ids are never reused, so a command for a removed loco cannot hit a
    /// new one.
    #[serde(skip)]
    last_id: u32,
    /// What the last import changed to fit the file (B-06).
    import_report: Vec<String>,
}

impl Session {
    pub fn locos(&self) -> &[LocoEntry] {
        &self.locos
    }

    pub fn station(&self) -> &Station {
        &self.station
    }

    pub(crate) fn set_connected(&mut self, connected: bool) {
        self.station.connected = connected;
    }

    /// Executes a command; on an error the session stays unchanged.
    /// [`Host::apply`](crate::host::Host::apply) handles connecting.
    pub(crate) fn apply(&mut self, command: Command) -> Result<(), CommandError> {
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
            Command::SetAxis { loco, deflection } => {
                self.entry(loco)?.axis = deflection.clamp(-1.0, 1.0)
            }
            Command::Reverse { loco } => self.entry(loco)?.motion.reverse(),
            Command::SetServer { host, port, bus } => self.set_server(host, port, bus)?,
            // Handled by Host::apply, which holds the driver.
            Command::Connect | Command::Disconnect => {}
            Command::ImportElectrip1 { path } => self.import_electrip1(&path)?,
        }
        Ok(())
    }

    /// Accelerates every loco with its axis for `seconds`; returns whether a
    /// speed changed.
    pub(crate) fn drive(&mut self, seconds: f64) -> bool {
        let mut changed = false;
        for entry in &mut self.locos {
            let before = entry.motion;
            entry
                .motion
                .accelerate(&entry.loco, entry.axis, DEAD_ZONE, seconds);
            changed |= entry.motion != before;
        }
        changed
    }

    /// Defaults of Electrip 1: DCC short, address 1, 128 steps, 100 km/h;
    /// [`Loco::new`] adds the rest.
    fn add_loco(&mut self) -> Result<(), LocoError> {
        let loco = Loco::new(Decoder::new(Protocol::DccShort, 1, 128)?, 100.0)?;
        self.push(loco);
        Ok(())
    }

    /// Appends a standing loco with a new id to the loco list.
    fn push(&mut self, loco: Loco) {
        self.last_id += 1;
        self.locos.push(LocoEntry {
            id: self.last_id,
            loco,
            motion: Motion::default(),
            axis: 0.0,
        });
    }

    fn import_electrip1(&mut self, path: &Path) -> Result<(), CommandError> {
        if self.station.connected {
            return Err(CommandError::Connected);
        }
        let import = electrip1::read(path).map_err(CommandError::Import)?;
        self.locos.clear();
        for loco in import.locos {
            self.push(loco);
        }
        self.station = import.station;
        self.import_report = import.report;
        Ok(())
    }

    fn set_server(&mut self, host: String, port: u16, bus: u16) -> Result<(), CommandError> {
        if self.station.connected {
            return Err(CommandError::Connected);
        }
        self.station = Station {
            host,
            port,
            bus,
            connected: false,
        };
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

    fn entry(&mut self, id: u32) -> Result<&mut LocoEntry, CommandError> {
        let index = self.index(id)?;
        Ok(&mut self.locos[index])
    }

    fn loco(&mut self, id: u32) -> Result<&mut Loco, CommandError> {
        Ok(&mut self.entry(id)?.loco)
    }
}

#[cfg(test)]
mod tests;
