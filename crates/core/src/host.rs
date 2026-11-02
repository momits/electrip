//! The session host (ADR 0010): it holds the session and the only
//! connection to the command station.

use crate::session::{Command, CommandError, Session, Station};
use crate::station::{CommandStation, StationError, StationEvent};

pub type Driver = Box<dyn CommandStation + Send>;

/// Opens a driver for the server in the session.
pub type Connector = Box<dyn FnMut(&Station) -> Result<Driver, StationError> + Send>;

pub struct Host {
    session: Session,
    driver: Option<Driver>,
    connect: Connector,
}

impl Host {
    pub fn new(connect: Connector) -> Self {
        Host {
            session: Session::default(),
            driver: None,
            connect,
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
                self.session.set_connected(true);
            }
            Command::Disconnect => self.disconnect(),
            command => self.session.apply(command)?,
        }
        Ok(())
    }

    /// Handles the events of the command station; returns whether the
    /// session changed.
    pub fn poll(&mut self) -> bool {
        let events = self.driver.as_mut().map(|d| d.events()).unwrap_or_default();
        let lost = events.contains(&StationEvent::Disconnected);
        if lost {
            self.disconnect();
        }
        lost
    }

    fn disconnect(&mut self) {
        self.driver = None;
        self.session.set_connected(false);
    }
}

#[cfg(test)]
mod tests;
