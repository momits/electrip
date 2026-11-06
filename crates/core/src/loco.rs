//! A loco with its decoder, maximum speed and speed curve. Changing the
//! maximum speed, the speed steps or the protocol changes the axes of the
//! curve and resets it, which needs a confirmation (B-09).
//! Changing or removing the sound model needs one, too (B-15).

use crate::decoder::{Decoder, DecoderError, Protocol};
use crate::event_sound::EventSound;
use crate::function::Function;
use crate::function_sound::SoundFunction;
use crate::sound::{Engine, EngineSound, SegmentSound, SoundModel, Steam};
use crate::speed_curve::SpeedCurve;
use serde::{Deserialize, Serialize};
use std::fmt;
use std::ops::RangeInclusive;
use std::path::{Path, PathBuf};

/// Name of a new loco, as in Electrip 1.
pub const DEFAULT_NAME: &str = "Unbenannte Lok";

/// Allowed maximum speed in km/h, as in Electrip 1.
pub const MAX_SPEED_RANGE: RangeInclusive<f64> = 1.0..=999.0;

/// Allowed acceleration and braking duration in seconds, as in Electrip 1.
pub const DURATION_RANGE: RangeInclusive<f64> = 1.0..=9999.0;

/// Allowed volume, from silent to full.
pub const VOLUME_RANGE: RangeInclusive<f64> = 0.0..=1.0;

#[derive(Debug, Clone, PartialEq)]
pub enum LocoError {
    Decoder(DecoderError),
    MaxSpeedOutOfRange,
    DurationOutOfRange,
    VolumeOutOfRange,
    /// The change would reset the speed curve and was not confirmed; nothing
    /// changed.
    ResetNotConfirmed,
    /// The change would reset the sounds and was not confirmed; nothing
    /// changed.
    SoundResetNotConfirmed,
    NoSound,
    UnknownSegment(usize),
    UnknownStroke(usize),
    SteamOutOfRange,
}

impl From<DecoderError> for LocoError {
    fn from(error: DecoderError) -> Self {
        LocoError::Decoder(error)
    }
}

impl fmt::Display for LocoError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            LocoError::Decoder(error) => error.fmt(f),
            LocoError::MaxSpeedOutOfRange => write!(
                f,
                "the maximum speed must be between {} and {} km/h",
                MAX_SPEED_RANGE.start(),
                MAX_SPEED_RANGE.end()
            ),
            LocoError::DurationOutOfRange => write!(
                f,
                "the duration must be between {} and {} s",
                DURATION_RANGE.start(),
                DURATION_RANGE.end()
            ),
            LocoError::VolumeOutOfRange => write!(
                f,
                "the volume must be between {} and {}",
                VOLUME_RANGE.start(),
                VOLUME_RANGE.end()
            ),
            LocoError::ResetNotConfirmed => write!(
                f,
                "this change resets the speed curve and needs a confirmation"
            ),
            LocoError::SoundResetNotConfirmed => write!(
                f,
                "this change resets the sounds of the loco and needs a confirmation"
            ),
            LocoError::NoSound => write!(f, "the loco has no sound"),
            LocoError::UnknownSegment(nr) => write!(f, "there is no sound segment {nr}"),
            LocoError::UnknownStroke(nr) => write!(f, "there is no cylinder stroke {nr}"),
            LocoError::SteamOutOfRange => write!(
                f,
                "strokes, wheel diameter, start delay or minimum frequency out of range"
            ),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Loco {
    name: String,
    decoder: Decoder,
    max_speed: f64,
    speed_curve: SpeedCurve,
    /// Seconds from standstill to Vmax at full acceleration.
    accel_duration: f64,
    /// Seconds from Vmax to standstill at full braking.
    brake_duration: f64,
    volume: f64,
    /// In the order the user sorted them (B-07).
    functions: Vec<Function>,
    /// In the order the user sorted them (B-16).
    #[serde(default)]
    sound_functions: Vec<SoundFunction>,
    /// Played only with a driving sound (B-17).
    #[serde(default)]
    event_sounds: Vec<EventSound>,
    /// Name of the picture in the media directory (B-05).
    picture: Option<String>,
    /// `None` is “no sound”.
    #[serde(default)]
    sound_model: Option<SoundModel>,
}

impl Loco {
    /// A loco named [`DEFAULT_NAME`] with a straight speed curve from
    /// standstill to Vmax and the durations and volume of Electrip 1.
    pub fn new(decoder: Decoder, max_speed: f64) -> Result<Self, LocoError> {
        check(MAX_SPEED_RANGE, max_speed, LocoError::MaxSpeedOutOfRange)?;
        Ok(Loco {
            name: DEFAULT_NAME.to_string(),
            decoder,
            max_speed,
            speed_curve: SpeedCurve::straight(max_speed, decoder.speed_steps().into()),
            accel_duration: 11.5,
            brake_duration: 8.5,
            volume: 0.8,
            functions: Vec::new(),
            sound_functions: Vec::new(),
            event_sounds: Vec::new(),
            picture: None,
            sound_model: None,
        })
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn set_name(&mut self, name: String) {
        self.name = name;
    }

    pub fn decoder(&self) -> &Decoder {
        &self.decoder
    }

    pub fn max_speed(&self) -> f64 {
        self.max_speed
    }

    pub fn speed_curve(&self) -> &SpeedCurve {
        &self.speed_curve
    }

    /// Edits of the curve itself keep it rising and need no confirmation.
    pub fn speed_curve_mut(&mut self) -> &mut SpeedCurve {
        &mut self.speed_curve
    }

    pub fn accel_duration(&self) -> f64 {
        self.accel_duration
    }

    pub fn set_accel_duration(&mut self, seconds: f64) -> Result<(), LocoError> {
        self.accel_duration = check(DURATION_RANGE, seconds, LocoError::DurationOutOfRange)?;
        Ok(())
    }

    pub fn brake_duration(&self) -> f64 {
        self.brake_duration
    }

    pub fn set_brake_duration(&mut self, seconds: f64) -> Result<(), LocoError> {
        self.brake_duration = check(DURATION_RANGE, seconds, LocoError::DurationOutOfRange)?;
        Ok(())
    }

    pub fn volume(&self) -> f64 {
        self.volume
    }

    pub fn set_volume(&mut self, volume: f64) -> Result<(), LocoError> {
        self.volume = check(VOLUME_RANGE, volume, LocoError::VolumeOutOfRange)?;
        Ok(())
    }

    pub fn functions(&self) -> &[Function] {
        &self.functions
    }

    pub fn functions_mut(&mut self) -> &mut Vec<Function> {
        &mut self.functions
    }

    pub fn sound_functions(&self) -> &[SoundFunction] {
        &self.sound_functions
    }

    pub fn sound_functions_mut(&mut self) -> &mut Vec<SoundFunction> {
        &mut self.sound_functions
    }

    pub fn event_sounds(&self) -> &[EventSound] {
        &self.event_sounds
    }

    pub fn event_sounds_mut(&mut self) -> &mut Vec<EventSound> {
        &mut self.event_sounds
    }

    pub fn picture(&self) -> Option<&str> {
        self.picture.as_deref()
    }

    pub fn set_picture(&mut self, picture: Option<String>) {
        self.picture = picture;
    }

    /// Replaces each sound file by `f` of it or with `None` removes it
    /// (B-20).
    pub(crate) fn map_sounds(&mut self, mut f: impl FnMut(&Path) -> Option<PathBuf>) {
        if let Some(model) = &mut self.sound_model {
            model.map_sounds(&mut f);
        }
        let functions = self.sound_functions.iter_mut().map(|s| &mut s.path);
        let events = self.event_sounds.iter_mut().map(|s| &mut s.path);
        for path in functions.chain(events) {
            *path = path.take().and_then(|p| f(&p));
        }
    }

    pub fn sound_model(&self) -> Option<&SoundModel> {
        self.sound_model.as_ref()
    }

    fn sound_model_mut(&mut self) -> Result<&mut SoundModel, LocoError> {
        self.sound_model.as_mut().ok_or(LocoError::NoSound)
    }

    /// Sets a new sound model with one segment, or none. Replacing a model of
    /// another engine resets its sounds and needs a confirmation.
    pub fn set_engine(&mut self, engine: Option<Engine>, confirmed: bool) -> Result<(), LocoError> {
        let current = self.sound_model.as_ref().map(SoundModel::engine);
        if current == engine {
            return Ok(());
        }
        if current.is_some() && !confirmed {
            return Err(LocoError::SoundResetNotConfirmed);
        }
        self.sound_model = engine.map(SoundModel::new);
        Ok(())
    }

    /// Replaces the sound model without asking, for imports.
    pub(crate) fn set_sound_model(&mut self, model: Option<SoundModel>) {
        self.sound_model = model;
    }

    pub fn set_engine_sound(
        &mut self,
        sound: EngineSound,
        path: Option<PathBuf>,
    ) -> Result<(), LocoError> {
        self.sound_model_mut()?.set_sound(sound, path);
        Ok(())
    }

    pub fn set_segment_sound(
        &mut self,
        nr: usize,
        sound: SegmentSound,
        path: Option<PathBuf>,
    ) -> Result<(), LocoError> {
        self.sound_model_mut()?.set_segment_sound(nr, sound, path)
    }

    pub fn set_stroke_sound(
        &mut self,
        nr: usize,
        stroke: usize,
        path: Option<PathBuf>,
    ) -> Result<(), LocoError> {
        self.sound_model_mut()?.set_stroke_sound(nr, stroke, path)
    }

    pub fn set_steam(&mut self, steam: Steam) -> Result<(), LocoError> {
        self.sound_model_mut()?.set_steam(steam)
    }

    /// See [`SoundModel::insert_segment`].
    pub fn insert_segment(&mut self, nr: usize) -> Result<(), LocoError> {
        let max_speed = self.max_speed;
        self.sound_model_mut()?.insert_segment(nr, max_speed)
    }

    /// See [`SoundModel::move_border`].
    pub fn move_segment_border(&mut self, nr: usize, speed: f64) -> Result<(), LocoError> {
        let max_speed = self.max_speed;
        self.sound_model_mut()?.move_border(nr, speed, max_speed)
    }

    /// Removes the `nr`-th sound segment. Removing the only one sets the
    /// loco to no sound and needs a confirmation.
    pub fn remove_segment(&mut self, nr: usize, confirmed: bool) -> Result<(), LocoError> {
        let model = self.sound_model_mut()?;
        if model.segments().len() > 1 {
            return model.remove_segment(nr);
        }
        model.check(nr)?;
        if !confirmed {
            return Err(LocoError::SoundResetNotConfirmed);
        }
        self.sound_model = None;
        Ok(())
    }

    pub fn set_address(&mut self, address: u16) -> Result<(), LocoError> {
        Ok(self.decoder.set_address(address)?)
    }

    pub fn set_max_speed(&mut self, max_speed: f64, confirmed: bool) -> Result<(), LocoError> {
        check(MAX_SPEED_RANGE, max_speed, LocoError::MaxSpeedOutOfRange)?;
        self.change_axes(confirmed, |loco| {
            loco.max_speed = max_speed;
            Ok(())
        })
    }

    pub fn set_speed_steps(&mut self, speed_steps: u8, confirmed: bool) -> Result<(), LocoError> {
        self.change_axes(confirmed, |loco| {
            Ok(loco.decoder.set_speed_steps(speed_steps)?)
        })
    }

    /// Switches the protocol like [`Decoder::set_protocol`]; this always sets
    /// the highest speed steps and so resets the curve.
    pub fn set_protocol(&mut self, protocol: Protocol, confirmed: bool) -> Result<(), LocoError> {
        self.change_axes(confirmed, |loco| {
            loco.decoder.set_protocol(protocol);
            Ok(())
        })
    }

    /// Applies a change of the curve's axes and resets the curve. Leaves the
    /// loco unchanged if nothing changes, the change fails or it is not
    /// confirmed.
    fn change_axes(
        &mut self,
        confirmed: bool,
        change: impl FnOnce(&mut Loco) -> Result<(), LocoError>,
    ) -> Result<(), LocoError> {
        let mut loco = self.clone();
        change(&mut loco)?;
        if loco == *self {
            return Ok(());
        }
        if !confirmed {
            return Err(LocoError::ResetNotConfirmed);
        }
        loco.speed_curve = SpeedCurve::straight(loco.max_speed, loco.decoder.speed_steps().into());
        if let Some(model) = &mut loco.sound_model {
            model.scale(loco.max_speed / self.max_speed);
        }
        *self = loco;
        Ok(())
    }
}

/// The value if it lies in the range, else the error.
fn check(range: RangeInclusive<f64>, value: f64, error: LocoError) -> Result<f64, LocoError> {
    if range.contains(&value) {
        Ok(value)
    } else {
        Err(error)
    }
}

#[cfg(test)]
mod tests;
