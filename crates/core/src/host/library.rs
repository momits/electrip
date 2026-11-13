//! The commands for the library of configurations (B-21). Every change of
//! the open configuration is saved at once.

use super::Host;
use crate::config::{self, Config, DEFAULT_NAME};
use crate::electrip1;
use crate::event_sound::EventSound;
use crate::function_sound::SoundFunction;
use crate::loco::Loco;
use crate::media;
use crate::package;
use crate::picture;
use crate::session::{Command, CommandError};
use std::fs;
use std::path::{Path, PathBuf};

impl Host {
    pub(super) fn open_first(&mut self) -> Result<(), CommandError> {
        fs::create_dir_all(&self.library)?;
        match config::names(&self.library)?.first() {
            Some(name) => self.open(name.clone()),
            None => self.create(DEFAULT_NAME.into(), Config::default()),
        }
    }

    /// Saves the open configuration if it changed.
    pub(super) fn save(&mut self) -> Result<(), CommandError> {
        let config = self.session.config();
        if config != self.saved {
            let path = config::path(&self.library, self.session.configuration());
            config::write(&path, &config)?;
            self.saved = config;
        }
        Ok(())
    }

    pub(super) fn create(&mut self, name: String, mut config: Config) -> Result<(), CommandError> {
        self.check_disconnected()?;
        config.id = config::new_id();
        config::write(&self.new_path(&name)?, &config)?;
        self.load(name, config, Vec::new())
    }

    pub(super) fn open(&mut self, name: String) -> Result<(), CommandError> {
        self.check_disconnected()?;
        let config = config::read(&self.path(&name)?)?;
        self.load(name, config, Vec::new())
    }

    /// Takes over the open configuration from its file after another
    /// instance changed it (N-04); the locos keep driving.
    pub fn reload(&mut self) -> Result<(), CommandError> {
        let path = config::path(&self.library, self.session.configuration());
        self.session.merge(config::read(&path)?);
        self.saved = self.session.config();
        Ok(())
    }

    /// The directory of the configuration files.
    pub fn library(&self) -> &Path {
        &self.library
    }

    pub(super) fn rename(&mut self, name: String) -> Result<(), CommandError> {
        let from = config::path(&self.library, self.session.configuration());
        fs::rename(from, self.new_path(&name)?)?;
        self.refresh(name)
    }

    pub(super) fn remove(&mut self, name: String) -> Result<(), CommandError> {
        if name == self.session.configuration() {
            return Err(CommandError::ConfigurationOpen(name));
        }
        fs::remove_file(self.path(&name)?)?;
        self.refresh(self.session.configuration().into())
    }

    pub(super) fn export(&self, path: &Path) -> Result<(), CommandError> {
        Ok(config::write(path, &self.saved)?)
    }

    pub(super) fn import(&mut self, path: &Path) -> Result<(), CommandError> {
        let name = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or_default();
        self.check_disconnected()?;
        let new_path = self.new_path(name)?;
        let mut import = electrip1::read(path).map_err(CommandError::Import)?;
        let folder = path.parent().unwrap_or(Path::new(""));
        for (loco, picture) in import.locos.iter_mut().zip(&import.pictures) {
            if let Some(picture) = picture {
                match picture::store(&self.library, &folder.join(picture), None) {
                    Ok(name) => loco.set_picture(Some(name)),
                    Err(error) => import.report.push(format!(
                        "{}: {error} ({})",
                        loco.name(),
                        picture.display()
                    )),
                }
            }
        }
        for loco in &import.locos {
            check_sounds(loco, &mut import.report);
        }
        let report = std::mem::take(&mut import.report);
        let config = Config::from(import);
        config::write(&new_path, &config)?;
        self.load(name.into(), config, report)
    }

    pub(super) fn export_loco(&mut self, loco: u32, path: &Path) -> Result<(), CommandError> {
        let loco = self.session.loco(loco)?.clone();
        Ok(package::write(
            path,
            &loco,
            self.session.actions(),
            &self.library,
        )?)
    }

    pub(super) fn import_loco(&mut self, path: &Path) -> Result<(), CommandError> {
        let package = package::read(path, &self.library).map_err(CommandError::Import)?;
        self.change(|session| {
            session.import_loco(package.loco, &package.actions, package.report);
            Ok(())
        })
    }

    /// Copies the sound file the command sets to the library, so other
    /// instances get it too (N-04); a file it cannot read stays as it is.
    pub(super) fn add_sound(&self, mut command: Command) -> Command {
        if let Command::SetEngineSound {
            path: Some(path), ..
        }
        | Command::SetSegmentSound {
            path: Some(path), ..
        }
        | Command::SetStrokeSound {
            path: Some(path), ..
        }
        | Command::AddSoundFunction {
            function: SoundFunction {
                path: Some(path), ..
            },
            ..
        }
        | Command::AddEventSound {
            sound: EventSound {
                path: Some(path), ..
            },
            ..
        } = &mut command
        {
            let added = fs::read(&*path).and_then(|b| media::add_sound(&self.library, &b, path));
            if let Ok(added) = added {
                *path = added;
            }
        }
        command
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
        let names = config::names(&self.library)?;
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

/// Names each sound of an imported loco that is missing in the report.
fn check_sounds(loco: &Loco, report: &mut Vec<String>) {
    for path in loco.sounds().iter().filter(|p| !p.is_file()) {
        let line = format!(
            "{}: cannot read the sound ({})",
            loco.name(),
            path.display()
        );
        if !report.contains(&line) {
            report.push(line);
        }
    }
}

#[cfg(test)]
mod tests;
