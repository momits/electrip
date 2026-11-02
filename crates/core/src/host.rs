//! The session host (ADR 0010): it holds the session and the only
//! connection to the command station.

use crate::session::{Command, CommandError, Session, Station};
use crate::station::{CommandStation, LocoState, StationError, StationEvent};
use std::collections::HashMap;

pub type Driver = Box<dyn CommandStation + Send>;

/// Opens a driver for the server in the session.
pub type Connector = Box<dyn FnMut(&Station) -> Result<Driver, StationError> + Send>;

pub struct Host {
    session: Session,
    driver: Option<Driver>,
    connect: Connector,
    /// The last state of each loco the driver knows, by loco id.
    sent: HashMap<u32, LocoState>,
}

impl Host {
    pub fn new(connect: Connector) -> Self {
        Host {
            session: Session::default(),
            driver: None,
            connect,
            sent: HashMap::new(),
        }
    }

    pub fn session(&self) -> &Session {
        &self.session
    }

    /// Executes a command; on an error the session stays unchanged.
    pub fn apply(&mut self, command: Command) -> Result<(), CommandError> {
        match command {
            Command::Connect => {
                let driver =
                    (self.connect)(self.session.station()).map_err(CommandError::Station)?;
                self.driver = Some(driver);
                self.sent = self
                    .session
                    .locos()
                    .iter()
                    .map(|e| (e.id, e.station_state()))
                    .collect();
                self.session.set_connected(true);
            }
            Command::Disconnect => self.disconnect(),
            command => self.session.apply(command)?,
        }
        Ok(())
    }

    /// Handles the events of the command station, then drives the locos
    /// for the `seconds` since the last call; returns whether the session
    /// changed.
    pub fn poll(&mut self, seconds: f64) -> bool {
        let events = self.driver.as_mut().map(|d| d.events()).unwrap_or_default();
        let lost = events.contains(&StationEvent::Disconnected);
        if lost {
            self.disconnect();
        }
        let driven = self.session.drive(seconds);
        self.send_locos();
        lost || driven
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

#[cfg(test)]
mod tests;
