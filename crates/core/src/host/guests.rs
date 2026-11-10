//! The configurations of guests (Q-016): a client that opened another
//! configuration drives the locos of the host with it. The driving state
//! belongs to the loco address: what one configuration changes, the locos
//! with the same address in the others take over.

use super::Host;
use crate::config::Config;
use crate::session::{Command, CommandError, Session};

impl Host {
    /// Adds the session of the configuration of a guest unless the host
    /// has it already; its locos take over the state of those with the
    /// same address.
    pub fn add_guest(&mut self, config: Config) {
        if self.sessions().any(|s| s.configuration_id() == config.id) {
            return;
        }
        let mut guest = self.session.guest(config);
        for entry in self.sessions().flat_map(Session::locos) {
            guest.adopt(entry.loco.decoder().address(), &entry.station_state());
        }
        self.guests.push(guest);
    }

    pub fn remove_guest(&mut self, configuration: &str) {
        self.guests
            .retain(|g| g.configuration_id() != configuration);
    }

    pub fn guest(&self, configuration: &str) -> Option<&Session> {
        self.guests
            .iter()
            .find(|g| g.configuration_id() == configuration)
    }

    /// The session a guest sees: its own locos and devices with the
    /// command station and audio targets of the host.
    pub fn guest_view(&self, configuration: &str) -> Option<Session> {
        let mut view = self.guest(configuration)?.clone();
        view.share(&self.session);
        Some(view)
    }

    /// Executes a command of a guest in the session of its configuration.
    pub fn apply_guest(
        &mut self,
        configuration: &str,
        command: Command,
    ) -> Result<(), CommandError> {
        let index = self
            .guests
            .iter()
            .position(|g| g.configuration_id() == configuration)
            .ok_or_else(|| CommandError::UnknownConfiguration(configuration.into()))?;
        self.apply_to(index + 1, command)
    }
}

/// Whether a guest may run the command: it drives but does not change its
/// configuration, which its own instance saves.
pub(super) fn drives(command: &Command) -> bool {
    matches!(
        command,
        Command::SetAxis { .. }
            | Command::Reverse { .. }
            | Command::EmergencyStop { .. }
            | Command::ToggleSound { .. }
            | Command::TriggerAction { .. }
            | Command::Input { .. }
            | Command::AddDevice { .. }
            | Command::RemoveDevice { .. }
            | Command::TogglePower
    )
}

#[cfg(test)]
mod tests;
