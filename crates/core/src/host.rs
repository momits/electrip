//! The session host (ADR 0010): it holds the session, the only
//! connection to the command station and the library of configurations.

use crate::config::Config;
use crate::picture;
use crate::session::{Command, CommandError, Session, Station};
use crate::station::{CommandStation, LocoState, StationError, StationEvent};
use std::collections::HashMap;
use std::path::PathBuf;

pub type Driver = Box<dyn CommandStation + Send>;

/// Opens a driver for the server in the session.
pub type Connector = Box<dyn FnMut(&Station) -> Result<Driver, StationError> + Send>;

pub struct Host {
    session: Session,
    driver: Option<Driver>,
    connect: Connector,
    /// The last state of each loco the driver knows, by loco id.
    sent: HashMap<u32, LocoState>,
    /// The directory of the configuration files (B-21).
    library: PathBuf,
    /// The open configuration as it was last saved.
    saved: Config,
}

impl Host {
    /// Opens the first configuration of the library; an empty library
    /// gets one.
    pub fn new(connect: Connector, library: PathBuf) -> Result<Self, CommandError> {
        let mut host = Host {
            session: Session::default(),
            driver: None,
            connect,
            sent: HashMap::new(),
            library,
            saved: Config::default(),
        };
        host.open_first()?;
        Ok(host)
    }

    pub fn session(&self) -> &Session {
        &self.session
    }

    /// Executes a command; on an error the session stays unchanged.
    pub fn apply(&mut self, command: Command) -> Result<(), CommandError> {
        match command {
            Command::Connect => self.connect()?,
            Command::Disconnect => self.disconnect(),
            Command::TogglePower => {
                let driver = self.driver.as_mut().ok_or(CommandError::Disconnected)?;
                let on = !self.session.station().track_power;
                driver.set_power(on).map_err(CommandError::Station)?;
                self.session.set_track_power(on);
            }
            Command::EmergencyStop { loco } => {
                let entry = self.session.emergency_stop(loco)?;
                let state = entry.station_state();
                if let Some(driver) = self.driver.as_mut() {
                    self.sent.insert(loco, state);
                    driver
                        .emergency_stop(entry.loco.decoder(), &state)
                        .map_err(CommandError::Station)?;
                }
            }
            Command::Input {
                device,
                control,
                value,
            } => {
                if let Some(command) = self.session.input(device, &control, value)? {
                    self.apply(command)?;
                }
            }
            Command::NewConfiguration { name } => self.create(name, Config::default())?,
            Command::OpenConfiguration { name } => self.open(name)?,
            Command::RenameConfiguration { name } => self.rename(name)?,
            Command::RemoveConfiguration { name } => self.remove(name)?,
            Command::ExportConfiguration { path } => self.export(&path)?,
            Command::ImportElectrip1 { path } => self.import(&path)?,
            Command::ExportLoco { loco, path } => self.export_loco(loco, &path)?,
            Command::ImportLoco { path } => self.import_loco(&path)?,
            Command::SetPicture { loco, path, crop } => {
                self.session.loco(loco)?;
                let picture =
                    picture::store(&self.media(), &path, crop).map_err(CommandError::Picture)?;
                self.change(|session| {
                    session.loco(loco)?.set_picture(Some(picture));
                    Ok(())
                })?;
            }
            command => self.change(|session| session.apply(command))?,
        }
        Ok(())
    }

    /// Changes the session and saves it; on an error both stay unchanged.
    fn change(
        &mut self,
        change: impl FnOnce(&mut Session) -> Result<(), CommandError>,
    ) -> Result<(), CommandError> {
        let before = self.session.clone();
        change(&mut self.session)?;
        if let Err(error) = self.save() {
            self.session = before;
            return Err(error);
        }
        Ok(())
    }

    /// Opens the driver and switches the track power on if the session
    /// says so.
    fn connect(&mut self) -> Result<(), CommandError> {
        let station = self.session.station();
        let power = station.power_on_start;
        let mut driver = (self.connect)(station).map_err(CommandError::Station)?;
        if power {
            driver.set_power(true).map_err(CommandError::Station)?;
        }
        self.driver = Some(driver);
        self.sent = self
            .session
            .locos()
            .iter()
            .map(|e| (e.id, e.station_state()))
            .collect();
        self.session.set_connected(true);
        self.session.set_track_power(power);
        Ok(())
    }

    /// Handles the events of the command station, then drives the locos
    /// for the `seconds` since the last call; returns whether the session
    /// changed.
    pub fn poll(&mut self, seconds: f64) -> bool {
        let events = self.driver.as_mut().map(|d| d.events()).unwrap_or_default();
        let mut changed = false;
        for event in events {
            match event {
                StationEvent::Power(on) => self.session.set_track_power(on),
                // Taken over with Q-010.
                StationEvent::Loco { .. } => continue,
                StationEvent::Disconnected => self.disconnect(),
            }
            changed = true;
        }
        let driven = self.session.drive(seconds);
        self.send_locos();
        changed || driven
    }

    /// Sends each loco whose state changed since the driver last got it.
    /// Locos are first sent after a change, so connecting or adding a loco
    /// does not stop a loco that another program drives.
    fn send_locos(&mut self) {
        let Some(driver) = self.driver.as_mut() else {
            return;
        };
        for entry in self.session.locos() {
            let state = entry.station_state();
            let last = self.sent.insert(entry.id, state);
            if last.is_some_and(|last| last != state) {
                // A broken connection arrives as an event and disconnects.
                let _ = driver.set_loco(entry.loco.decoder(), &state);
            }
        }
    }

    fn disconnect(&mut self) {
        self.driver = None;
        self.session.set_connected(false);
    }
}

mod library;
#[cfg(test)]
mod tests;
