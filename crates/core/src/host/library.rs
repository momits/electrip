//! The commands for the library of configurations (B-21). Every change of
//! the open configuration is saved at once.

use super::Host;
use crate::config::{self, Config, DEFAULT_NAME};
use crate::electrip1;
use crate::session::CommandError;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

fn file_error(error: io::Error) -> CommandError {
    CommandError::File(error.to_string())
}

impl Host {
    pub(super) fn open_first(&mut self) -> Result<(), CommandError> {
        fs::create_dir_all(&self.library).map_err(file_error)?;
        match config::names(&self.library).map_err(file_error)?.first() {
            Some(name) => self.open(name.clone()),
            None => self.create(DEFAULT_NAME.into(), Config::default()),
        }
    }

    /// Saves the open configuration if it changed.
    pub(super) fn save(&mut self) -> Result<(), CommandError> {
        let config = self.session.config();
        if config != self.saved {
            let path = config::path(&self.library, self.session.configuration());
            config::write(&path, &config).map_err(file_error)?;
            self.saved = config;
        }
        Ok(())
    }

    pub(super) fn create(&mut self, name: String, config: Config) -> Result<(), CommandError> {
        self.check_disconnected()?;
        config::write(&self.new_path(&name)?, &config).map_err(file_error)?;
        self.load(name, config, Vec::new())
    }

    pub(super) fn open(&mut self, name: String) -> Result<(), CommandError> {
        self.check_disconnected()?;
        let config = config::read(&self.path(&name)?).map_err(file_error)?;
        self.load(name, config, Vec::new())
    }

    pub(super) fn rename(&mut self, name: String) -> Result<(), CommandError> {
        let from = config::path(&self.library, self.session.configuration());
        fs::rename(from, self.new_path(&name)?).map_err(file_error)?;
        self.refresh(name)
    }

    pub(super) fn remove(&mut self, name: String) -> Result<(), CommandError> {
        if name == self.session.configuration() {
            return Err(CommandError::ConfigurationOpen(name));
        }
        fs::remove_file(self.path(&name)?).map_err(file_error)?;
        self.refresh(self.session.configuration().into())
    }

    pub(super) fn export(&self, path: &Path) -> Result<(), CommandError> {
        config::write(path, &self.saved).map_err(file_error)
    }

    pub(super) fn import(&mut self, path: &Path) -> Result<(), CommandError> {
        let name = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or_default();
        self.check_disconnected()?;
        let new_path = self.new_path(name)?;
        let import = electrip1::read(path).map_err(CommandError::Import)?;
        let config = Config {
            locos: import.locos,
            station: import.station,
            ..Config::default()
        };
        config::write(&new_path, &config).map_err(file_error)?;
        self.load(name.into(), config, import.report)
    }

    fn load(
        &mut self,
        name: String,
        config: Config,
        report: Vec<String>,
    ) -> Result<(), CommandError> {
        self.session.load(config, report);
        self.saved = self.session.config();
        self.refresh(name)
    }

    /// Reads the names of the configurations again.
    fn refresh(&mut self, open: String) -> Result<(), CommandError> {
        let names = config::names(&self.library).map_err(file_error)?;
        self.session.set_configurations(open, names);
        Ok(())
    }

    fn check_disconnected(&self) -> Result<(), CommandError> {
        if self.session.station().connected {
            return Err(CommandError::Connected);
        }
        Ok(())
    }

    /// The file for a new configuration `name`.
    fn new_path(&self, name: &str) -> Result<PathBuf, CommandError> {
        let path = self.path(name)?;
        if path.exists() {
            return Err(CommandError::ConfigurationExists(name.into()));
        }
        Ok(path)
    }

    /// The file of the configuration `name`; names that are no file names
    /// cannot reach a file outside the library.
    fn path(&self, name: &str) -> Result<PathBuf, CommandError> {
        if !config::valid_name(name) {
            return Err(CommandError::InvalidName(name.into()));
        }
        Ok(config::path(&self.library, name))
    }
}

#[cfg(test)]
mod tests;
