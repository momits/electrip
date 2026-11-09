//! The state of a session and the commands that change it (ADR 0002). UI,
//! gamepads, the control channel and tests change the state only through
//! [`Host::apply`](crate::host::Host::apply).

use crate::audio::AudioSink;
use crate::config::{Config, View};
use crate::decoder::{Decoder, Protocol};
use crate::drive::{self, DEAD_ZONE, Motion};
use crate::driving_sound::DrivingSound;
use crate::electrip1::ImportError;
use crate::event_sound::{self, EventSound};
use crate::function::{Action, Function};
use crate::function_sound::SoundFunction;
use crate::input::{Device, Mapping, Target};
use crate::loco::{Loco, LocoError};
use crate::picture::{Crop, PictureError};
use crate::sound::{Engine, EngineSound, SegmentSound, Steam};
use crate::station::{LocoState, MAX_FUNCTION, StationError, StationKind};
use serde::{Deserialize, Serialize};
use std::fmt;
use std::io;
use std::path::PathBuf;
use std::time::Duration;

/// A user action. Locos are addressed by their id in the session.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
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
    /// Loads the image at `path` on the host and saves the crop, by default
    /// the largest one in the middle, as the loco's picture (B-05).
    SetPicture {
        loco: u32,
        path: PathBuf,
        crop: Option<Crop>,
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
    /// Sets a new sound model with one segment, or none with `engine`
    /// `null` (B-15).
    SetEngine {
        loco: u32,
        engine: Option<Engine>,
        #[serde(default)]
        confirmed: bool,
    },
    /// Splits the sound segment `segment` (from 0) in the middle.
    InsertSegment {
        loco: u32,
        segment: usize,
    },
    RemoveSegment {
        loco: u32,
        segment: usize,
        #[serde(default)]
        confirmed: bool,
    },
    /// Moves the border where the sound segment begins to `speed` in km/h.
    MoveSegmentBorder {
        loco: u32,
        segment: usize,
        speed: f64,
    },
    /// Sets a sound file on the host for the engine at standstill (B-12);
    /// `null` removes it.
    SetEngineSound {
        loco: u32,
        sound: EngineSound,
        path: Option<PathBuf>,
    },
    /// Sets a sound file on the host for the sound segment (B-11); `null`
    /// removes it.
    SetSegmentSound {
        loco: u32,
        segment: usize,
        sound: SegmentSound,
        path: Option<PathBuf>,
    },
    /// Sets a sound file on the host for the `stroke`-th cylinder stroke
    /// (from 0) of a steam engine in the sound segment (B-14); `null`
    /// removes it.
    SetStrokeSound {
        loco: u32,
        segment: usize,
        stroke: usize,
        path: Option<PathBuf>,
    },
    /// How the steam engine strokes (B-14).
    SetSteam {
        loco: u32,
        steam: Steam,
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
    /// Switches the driving sound of the loco on or off (B-02, B-11).
    ToggleSound {
        loco: u32,
    },
    /// Adds a logical action (N-07).
    AddAction {
        name: String,
    },
    RenameAction {
        action: u32,
        name: String,
    },
    /// Removes the action and every function mapped to it.
    RemoveAction {
        action: u32,
    },
    /// Appends a mapping of an action to a decoder function (B-07).
    AddFunction {
        loco: u32,
        function: Function,
    },
    RemoveFunction {
        loco: u32,
        index: usize,
    },
    /// Moves a function to `position` (from 0) in the list of the loco.
    MoveFunction {
        loco: u32,
        index: usize,
        position: usize,
    },
    /// Appends a sound function (B-16).
    AddSoundFunction {
        loco: u32,
        function: SoundFunction,
    },
    RemoveSoundFunction {
        loco: u32,
        index: usize,
    },
    /// Moves a sound function to `position` (from 0) in the list of the
    /// loco.
    MoveSoundFunction {
        loco: u32,
        index: usize,
        position: usize,
    },
    /// Appends an event sound (B-17), as active as at the start.
    AddEventSound {
        loco: u32,
        sound: EventSound,
    },
    RemoveEventSound {
        loco: u32,
        index: usize,
    },
    /// Presses (`pressed`) or releases an action for a loco; it switches
    /// the functions, sound functions and event sounds of the loco mapped
    /// to it.
    TriggerAction {
        loco: u32,
        action: u32,
        pressed: bool,
    },
    /// Where the command station is; only while disconnected.
    SetServer {
        #[serde(default)]
        kind: StationKind,
        host: String,
        port: u16,
        bus: u16,
    },
    /// Whether connecting switches the track power on (B-23).
    SetPowerOnStart {
        on: bool,
    },
    /// The options of the control view (B-22).
    SetView {
        view: View,
    },
    /// Connects to the server; the host also replaces an open connection.
    Connect,
    Disconnect,
    /// The emergency stop of the layout: switches the track power off, the
    /// next time on again; only while connected (B-23).
    TogglePower,
    /// Stops only this loco at once; the track power stays on (B-23).
    EmergencyStop {
        loco: u32,
    },
    /// Connects an input device (N-01). The caller chooses the id; `kind`
    /// names the device type whose mapping it uses. The device controls
    /// the first loco no other device controls.
    AddDevice {
        device: u32,
        kind: String,
    },
    /// Disconnects the device; its loco keeps its speed.
    RemoveDevice {
        device: u32,
    },
    /// Maps a control of all devices of `kind` to `target` (B-02).
    Bind {
        kind: String,
        control: String,
        target: Target,
    },
    Unbind {
        kind: String,
        control: String,
    },
    /// A control of a device moved: buttons and hat directions 1 pressed
    /// and 0 released, axes from -1 to 1 with up negative like SDL.
    Input {
        device: u32,
        control: String,
        value: f64,
    },
    /// Creates an empty configuration in the library and opens it; only
    /// while disconnected (B-21).
    NewConfiguration {
        name: String,
    },
    /// Opens a configuration of the library; only while disconnected.
    OpenConfiguration {
        name: String,
    },
    /// Renames the open configuration.
    RenameConfiguration {
        name: String,
    },
    /// Deletes a configuration other than the open one.
    RemoveConfiguration {
        name: String,
    },
    /// Writes the open configuration to a file on the host.
    ExportConfiguration {
        path: PathBuf,
    },
    /// Writes the loco with its picture as a package to a file on the host
    /// (B-20).
    ExportLoco {
        loco: u32,
        path: PathBuf,
    },
    /// Appends the loco of a package of Electrip 2 or 1 on the host; its
    /// picture goes to the library.
    ImportLoco {
        path: PathBuf,
    },
    /// Imports a configuration file of Electrip 1 on the host as a new
    /// configuration named like the file and opens it; only while
    /// disconnected.
    ImportElectrip1 {
        path: PathBuf,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub enum CommandError {
    UnknownLoco(u32),
    UnknownAction(u32),
    UnknownDevice(u32),
    DeviceExists(u32),
    PositionOutOfRange(usize),
    FunctionOutOfRange(u8),
    Loco(LocoError),
    Connected,
    Disconnected,
    Station(StationError),
    Import(ImportError),
    Picture(PictureError),
    InvalidName(String),
    ConfigurationExists(String),
    ConfigurationOpen(String),
    File(String),
}

impl From<LocoError> for CommandError {
    fn from(error: LocoError) -> Self {
        CommandError::Loco(error)
    }
}

impl From<io::Error> for CommandError {
    fn from(error: io::Error) -> Self {
        CommandError::File(error.to_string())
    }
}

impl fmt::Display for CommandError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            CommandError::UnknownLoco(id) => write!(f, "there is no loco with id {id}"),
            CommandError::UnknownAction(id) => write!(f, "there is no action with id {id}"),
            CommandError::UnknownDevice(id) => write!(f, "there is no device with id {id}"),
            CommandError::DeviceExists(id) => write!(f, "there is already a device with id {id}"),
            CommandError::PositionOutOfRange(position) => {
                write!(f, "there is no position {position} in the list")
            }
            CommandError::FunctionOutOfRange(number) => {
                write!(f, "F{number} lies above F{MAX_FUNCTION}")
            }
            CommandError::Loco(error) => error.fmt(f),
            CommandError::Connected => f.write_str("disconnect from the command station first"),
            CommandError::Disconnected => f.write_str("connect to the command station first"),
            CommandError::Station(error) => error.fmt(f),
            CommandError::Import(error) => error.fmt(f),
            CommandError::Picture(error) => error.fmt(f),
            CommandError::InvalidName(name) => write!(f, "{name:?} cannot name a configuration"),
            CommandError::ConfigurationExists(name) => {
                write!(f, "there is already a configuration {name:?}")
            }
            CommandError::ConfigurationOpen(name) => {
                write!(f, "the configuration {name:?} is open")
            }
            CommandError::File(reason) => write!(f, "file error: {reason}"),
        }
    }
}

/// The command station and whether the host is connected to it (B-01,
/// N-02). Read from a file, missing values get the defaults and it is
/// disconnected.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct Station {
    pub kind: StationKind,
    pub host: String,
    pub port: u16,
    pub bus: u16,
    /// Electrip 1 calls it `power`.
    #[serde(alias = "power")]
    pub power_on_start: bool,
    #[serde(skip_deserializing)]
    pub connected: bool,
    /// As the command station last reported it; off while disconnected.
    #[serde(skip_deserializing)]
    pub track_power: bool,
}

/// Defaults of Electrip 1.
impl Default for Station {
    fn default() -> Self {
        Station {
            kind: StationKind::Srcp,
            host: "localhost".into(),
            port: 4303,
            bus: 1,
            power_on_start: true,
            connected: false,
            track_power: false,
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
    /// Off at the start like Electrip 1.
    pub sound: DrivingSound,
    /// The deflection of the drive axis, 0 within the dead zone.
    #[serde(skip)]
    axis: f64,
}

impl LocoEntry {
    /// What the command station gets: the speed step from the speed curve,
    /// cut off like Electrip 1, and the functions that are on.
    pub fn station_state(&self) -> LocoState {
        let curve = self.loco.speed_curve();
        let step = curve.step_at(self.motion.speed()).unwrap_or(0.0);
        let mut state = LocoState {
            forward: self.motion.forward(),
            step: step as u8,
            functions: 0,
        };
        for function in self.loco.functions().iter().filter(|f| f.on) {
            state.set_function(function.number, true);
        }
        state
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct Session {
    locos: Vec<LocoEntry>,
    /// The logical actions in the order they were added (N-07).
    actions: Vec<Action>,
    /// One mapping per device type, in the order they were first used.
    mappings: Vec<Mapping>,
    devices: Vec<Device>,
    station: Station,
    view: View,
    /// Ids are never reused, so a command for a removed loco cannot hit a
    /// new one.
    #[serde(skip)]
    last_id: u32,
    #[serde(skip)]
    last_action_id: u32,
    /// What the last import changed to fit the file (B-06).
    import_report: Vec<String>,
    /// The name of the open configuration (B-21).
    configuration: String,
    /// The names of all configurations in the library, sorted.
    configurations: Vec<String>,
}

impl Session {
    pub fn locos(&self) -> &[LocoEntry] {
        &self.locos
    }

    pub fn station(&self) -> &Station {
        &self.station
    }

    pub fn configuration(&self) -> &str {
        &self.configuration
    }

    /// The part of the session that is saved; functions in their default
    /// state, the station disconnected.
    pub fn config(&self) -> Config {
        let mut locos: Vec<Loco> = self.locos.iter().map(|e| e.loco.clone()).collect();
        for loco in &mut locos {
            for function in loco.functions_mut() {
                function.on = function.default_on;
            }
            for function in loco.sound_functions_mut() {
                *function = function.off();
            }
            for sound in loco.event_sounds_mut() {
                *sound = sound.reset();
            }
        }
        let station = Station {
            connected: false,
            track_power: false,
            ..self.station.clone()
        };
        Config {
            locos,
            actions: self.actions.clone(),
            mappings: self.mappings.clone(),
            station,
            view: self.view,
        }
    }

    /// Replaces the configuration; the locos stand and get new ids, the
    /// devices keep their locos if they can and get a mapping if their type
    /// has none.
    pub(crate) fn load(&mut self, config: Config, report: Vec<String>) {
        self.locos.clear();
        for loco in config.locos {
            self.push(loco);
        }
        self.last_action_id = config.actions.iter().map(|a| a.id).max().unwrap_or(0);
        self.actions = config.actions;
        self.mappings = config.mappings;
        let kinds: Vec<_> = self.devices.iter().map(|d| d.kind.clone()).collect();
        for kind in kinds {
            self.mapping(kind);
        }
        self.station = config.station;
        self.view = config.view;
        self.import_report = report;
        self.assign_locos();
    }

    pub(crate) fn set_configurations(&mut self, open: String, names: Vec<String>) {
        self.configuration = open;
        self.configurations = names;
    }

    pub(crate) fn set_connected(&mut self, connected: bool) {
        self.station.connected = connected;
        self.station.track_power &= connected;
    }

    pub(crate) fn set_track_power(&mut self, on: bool) {
        self.station.track_power = on;
    }

    /// Stops the loco at once and releases its axis.
    pub(crate) fn emergency_stop(&mut self, id: u32) -> Result<&LocoEntry, CommandError> {
        let entry = self.entry(id)?;
        entry.motion.stop();
        entry.axis = 0.0;
        Ok(entry)
    }

    /// Takes over the speed step, direction and functions the command
    /// station reports for `address`, e.g. after another program changed
    /// them; a deflected axis ramps on from there (Q-010). Returns the id
    /// and the new station state of each loco with the address.
    pub(crate) fn adopt(&mut self, address: u16, state: &LocoState) -> Vec<(u32, LocoState)> {
        let mut adopted = Vec::new();
        for entry in &mut self.locos {
            if entry.loco.decoder().address() != address {
                continue;
            }
            let speed = entry.loco.speed_curve().speed_of_step(state.step);
            entry.motion = Motion::new(speed, state.forward);
            for function in entry.loco.functions_mut() {
                function.on = state.function(function.number);
            }
            adopted.push((entry.id, entry.station_state()));
        }
        adopted
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
            Command::SetEngine {
                loco,
                engine,
                confirmed,
            } => self.loco(loco)?.set_engine(engine, confirmed)?,
            Command::InsertSegment { loco, segment } => self.loco(loco)?.insert_segment(segment)?,
            Command::RemoveSegment {
                loco,
                segment,
                confirmed,
            } => self.loco(loco)?.remove_segment(segment, confirmed)?,
            Command::MoveSegmentBorder {
                loco,
                segment,
                speed,
            } => self.loco(loco)?.move_segment_border(segment, speed)?,
            Command::SetEngineSound { loco, sound, path } => {
                self.loco(loco)?.set_engine_sound(sound, path)?
            }
            Command::SetSegmentSound {
                loco,
                segment,
                sound,
                path,
            } => self.loco(loco)?.set_segment_sound(segment, sound, path)?,
            Command::SetStrokeSound {
                loco,
                segment,
                stroke,
                path,
            } => self.loco(loco)?.set_stroke_sound(segment, stroke, path)?,
            Command::SetSteam { loco, steam } => self.loco(loco)?.set_steam(steam)?,
            Command::SetAxis { loco, deflection } => self.set_axis(loco, deflection, DEAD_ZONE)?,
            Command::Reverse { loco } => self.entry(loco)?.motion.reverse(),
            Command::AddAction { name } => self.add_action(name),
            Command::RenameAction { action, name } => self.action(action)?.name = name,
            Command::RemoveAction { action } => self.remove_action(action)?,
            Command::AddFunction { loco, function } => self.add_function(loco, function)?,
            Command::RemoveFunction { loco, index } => {
                remove(self.loco(loco)?.functions_mut(), index)?
            }
            Command::MoveFunction {
                loco,
                index,
                position,
            } => move_item(self.loco(loco)?.functions_mut(), index, position)?,
            Command::AddSoundFunction { loco, function } => {
                self.add_sound_function(loco, function)?
            }
            Command::RemoveSoundFunction { loco, index } => {
                remove(self.loco(loco)?.sound_functions_mut(), index)?
            }
            Command::MoveSoundFunction {
                loco,
                index,
                position,
            } => move_item(self.loco(loco)?.sound_functions_mut(), index, position)?,
            Command::AddEventSound { loco, sound } => self.add_event_sound(loco, sound)?,
            Command::RemoveEventSound { loco, index } => {
                remove(self.loco(loco)?.event_sounds_mut(), index)?
            }
            Command::SetServer {
                kind,
                host,
                port,
                bus,
            } => self.set_server(Station {
                kind,
                host,
                port,
                bus,
                ..self.station.clone()
            })?,
            Command::SetPowerOnStart { on } => self.station.power_on_start = on,
            Command::SetView { view } => self.view = view,
            // Handled by Host::apply, which holds the driver and the library.
            Command::Connect
            | Command::Disconnect
            | Command::TogglePower
            | Command::EmergencyStop { .. }
            | Command::ToggleSound { .. }
            | Command::TriggerAction { .. }
            | Command::SetPicture { .. }
            | Command::Input { .. }
            | Command::NewConfiguration { .. }
            | Command::OpenConfiguration { .. }
            | Command::RenameConfiguration { .. }
            | Command::RemoveConfiguration { .. }
            | Command::ExportConfiguration { .. }
            | Command::ImportElectrip1 { .. }
            | Command::ExportLoco { .. }
            | Command::ImportLoco { .. } => {}
            Command::AddDevice { device, kind } => self.add_device(device, kind)?,
            Command::RemoveDevice { device } => self.remove_device(device)?,
            Command::Bind {
                kind,
                control,
                target,
            } => self.bind(kind, control, target)?,
            Command::Unbind { kind, control } => self.mapping(kind).unbind(&control),
        }
        self.assign_locos();
        Ok(())
    }

    fn set_axis(&mut self, loco: u32, deflection: f64, dead_zone: f64) -> Result<(), CommandError> {
        self.entry(loco)?.axis = drive::deflection(deflection, dead_zone);
        Ok(())
    }

    pub(crate) fn toggle_sound(
        &mut self,
        id: u32,
        sink: &mut dyn AudioSink,
    ) -> Result<(), CommandError> {
        let entry = self.entry(id)?;
        let speed = entry.motion.speed();
        entry.sound.toggle(entry.loco.sound_model(), speed, sink);
        Ok(())
    }

    /// Changes the locos of held "previous/next loco" controls,
    /// accelerates every loco with its axis and plays its sounds for
    /// `seconds`; returns whether the session changed.
    pub(crate) fn drive(&mut self, seconds: f64, sink: &mut dyn AudioSink) -> bool {
        let mut changed = self.scroll(seconds);
        let elapsed = Duration::try_from_secs_f64(seconds).unwrap_or_default();
        for entry in &mut self.locos {
            let before = (entry.motion, entry.sound.state());
            if !entry.sound.locks_speed() {
                entry.motion.accelerate(&entry.loco, entry.axis, seconds);
            }
            let (model, speed) = (entry.loco.sound_model(), entry.motion.speed());
            entry.sound.play(model, speed, sink, elapsed);
            let accel = (speed - before.0.speed()) / seconds.max(f64::MIN_POSITIVE);
            let motion = model.is_some().then_some((entry.motion, accel));
            changed |= (entry.motion, entry.sound.state()) != before;
            for function in entry.loco.sound_functions_mut() {
                changed |= function.play(sink, elapsed);
            }
            let sounds = entry.loco.event_sounds_mut();
            event_sound::play(sounds, entry.id, motion, sink, elapsed);
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
            sound: DrivingSound::new(self.last_id),
            axis: 0.0,
        });
    }

    fn set_server(&mut self, station: Station) -> Result<(), CommandError> {
        if self.station.connected {
            return Err(CommandError::Connected);
        }
        self.station = station;
        Ok(())
    }

    fn move_loco(&mut self, id: u32, position: usize) -> Result<(), CommandError> {
        let index = self.index(id)?;
        move_item(&mut self.locos, index, position)
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

    pub(crate) fn loco(&mut self, id: u32) -> Result<&mut Loco, CommandError> {
        Ok(&mut self.entry(id)?.loco)
    }
}

fn remove<T>(list: &mut Vec<T>, index: usize) -> Result<(), CommandError> {
    check_index(list, index)?;
    list.remove(index);
    Ok(())
}

/// Moves the item at `index` to `position`.
fn move_item<T>(list: &mut Vec<T>, index: usize, position: usize) -> Result<(), CommandError> {
    check_index(list, index)?;
    check_index(list, position)?;
    let item = list.remove(index);
    list.insert(position, item);
    Ok(())
}

/// An error unless `index` points into `list`.
fn check_index<T>(list: &[T], index: usize) -> Result<(), CommandError> {
    if index < list.len() {
        Ok(())
    } else {
        Err(CommandError::PositionOutOfRange(index))
    }
}

mod actions;
mod devices;
#[cfg(test)]
mod tests;
