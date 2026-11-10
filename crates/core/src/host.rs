//! The session host (ADR 0010): it holds the session, the only
//! connection to the command station and the library of configurations.

use crate::audio::{Audio, AudioSink, Remote, Targets};
use crate::config::Config;
use crate::decoder::Decoder;
use crate::media::LibrarySink;
use crate::picture;
use crate::session::{Command, CommandError, Session, Station};
use crate::station::{CommandStation, LocoState, StationError, StationEvent};
use echoes::Echoes;
use std::collections::HashMap;
use std::path::PathBuf;

pub type Driver = Box<dyn CommandStation + Send>;

/// Opens a driver for the server in the session.
pub type Connector = Box<dyn FnMut(&Station) -> Result<Driver, StationError> + Send>;

pub struct Host {
    session: Session,
    driver: Option<Driver>,
    connect: Connector,
    audio: Targets,
    /// The last state of each loco the driver knows, by loco id.
    sent: HashMap<u32, LocoState>,
    /// The decoder the driver was last asked about, by loco id.
    requested: HashMap<u32, Decoder>,
    echoes: Echoes,
    /// The directory of the configuration files (B-21).
    library: PathBuf,
    /// The open configuration as it was last saved.
    saved: Config,
}

impl Host {
    /// Opens the first configuration of the library; an empty library
    /// gets one.
    pub fn new(connect: Connector, audio: Audio, library: PathBuf) -> Result<Self, CommandError> {
        let mut host = Host {
            session: Session::default(),
            driver: None,
            connect,
            audio: Targets::new(Box::new(LibrarySink {
                sink: audio,
                library: library.clone(),
            })),
            sent: HashMap::new(),
            requested: HashMap::new(),
            echoes: Echoes::default(),
            library,
            saved: Config::default(),
        };
        host.open_first()?;
        let devices = host.audio.devices();
        host.session.set_audio_devices(devices);
        Ok(host)
    }

    pub fn session(&self) -> &Session {
        &self.session
    }

    /// Executes a command; on an error the session stays unchanged.
    pub fn apply(&mut self, command: Command) -> Result<(), CommandError> {
        self.route_audio();
        match self.add_sound(command) {
            Command::Connect => self.connect(self.session.station().power_on_start)?,
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
                    let before = self.sent.insert(loco, state);
                    let address = entry.loco.decoder().address();
                    self.echoes.note(address, before, state);
                    driver
                        .emergency_stop(entry.loco.decoder(), &state)
                        .map_err(CommandError::Station)?;
                }
            }
            Command::ToggleSound { loco } => self.session.toggle_sound(loco, &mut self.audio)?,
            Command::TriggerAction {
                loco,
                action,
                pressed,
            } => {
                let audio = &mut self.audio;
                self.session.trigger_action(loco, action, pressed, audio)?
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

    /// Plays the sounds of the locos that name `instance` there while it
    /// is connected; it offers `devices` (N-05).
    pub fn add_audio_target(&mut self, instance: String, devices: Vec<String>, remote: Remote) {
        self.session
            .audio_targets_mut()
            .insert(instance.clone(), devices);
        self.audio.add(instance, remote);
    }

    /// The host plays the sounds of the locos that name `instance` itself.
    pub fn remove_audio_target(&mut self, instance: &str) {
        self.session.audio_targets_mut().remove(instance);
        self.audio.remove(instance);
    }

    /// Tells the audio targets where each loco plays (N-05).
    fn route_audio(&mut self) {
        for entry in self.session.locos() {
            let loco = &entry.loco;
            self.audio
                .route(entry.id, loco.audio_instance(), loco.audio_device());
        }
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

    /// Connects as a new host after the old one is gone (N-03, ADR 0010):
    /// reads back the track power and the locos without switching the
    /// power on.
    pub fn take_over(&mut self) -> Result<(), CommandError> {
        self.connect(false)
    }

    /// Opens the driver and switches the track power on if `power`.
    fn connect(&mut self, power: bool) -> Result<(), CommandError> {
        let mut driver = (self.connect)(self.session.station()).map_err(CommandError::Station)?;
        if power {
            driver.set_power(true).map_err(CommandError::Station)?;
        }
        self.driver = Some(driver);
        self.requested.clear();
        self.send_locos();
        self.session.set_connected(true);
        self.session.set_track_power(power);
        Ok(())
    }

    /// Handles the events of the command station, then drives the locos
    /// for the `seconds` since the last call; returns whether the session
    /// changed.
    pub fn poll(&mut self, seconds: f64) -> bool {
        self.echoes.tick(seconds);
        let events = self.driver.as_mut().map(|d| d.events()).unwrap_or_default();
        let mut changed = false;
        for event in events {
            changed |= match event {
                StationEvent::Power(on) => {
                    self.session.set_track_power(on);
                    true
                }
                StationEvent::Loco { address, state } => self.adopt(address, &state),
                StationEvent::Disconnected => {
                    self.disconnect();
                    true
                }
            };
        }
        self.route_audio();
        let driven = self.session.drive(seconds, &mut self.audio);
        self.send_locos();
        changed || driven
    }

    /// Takes over a loco state that the host did not send itself as the
    /// new starting point (ADR 0010) without sending it back.
    fn adopt(&mut self, address: u16, state: &LocoState) -> bool {
        if self.echoes.contains(address, state) {
            return false;
        }
        let adopted = self.session.adopt(address, state);
        self.sent.extend(adopted.iter().copied());
        !adopted.is_empty()
    }

    /// Sends each loco whose state changed since the driver last got it.
    /// A loco that is new to the driver or has a new decoder is asked for
    /// instead, so the host takes over what it does (ADR 0010) and does not
    /// stop a loco that another program drives.
    fn send_locos(&mut self) {
        let Some(driver) = self.driver.as_mut() else {
            return;
        };
        for entry in self.session.locos() {
            let decoder = entry.loco.decoder();
            if self.requested.insert(entry.id, *decoder) != Some(*decoder) {
                self.sent.insert(entry.id, entry.station_state());
                // A broken connection arrives as an event and disconnects.
                let _ = driver.request_loco(decoder);
                continue;
            }
            let mut state = entry.station_state();
            if let Some(last) = self.sent.get(&entry.id) {
                state = entry.sound.synchronize(state, last);
            }
            let last = self.sent.insert(entry.id, state);
            if last.is_some_and(|last| last != state) {
                self.echoes.note(decoder.address(), last, state);
                // A broken connection arrives as an event and disconnects.
                let _ = driver.set_loco(decoder, &state);
            }
        }
    }

    fn disconnect(&mut self) {
        self.driver = None;
        self.session.set_connected(false);
    }
}

mod echoes;
mod library;
#[cfg(test)]
mod tests;
