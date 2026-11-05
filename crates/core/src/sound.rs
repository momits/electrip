//! The sound model of a loco (B-15): a combustion or steam engine whose
//! speed range from standstill to Vmax is split into segments, each with
//! its own sounds. Like in Electrip 1 a new model has one segment over the
//! whole range.

use crate::loco::LocoError;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::f64::consts::PI;
use std::ops::RangeInclusive;
use std::path::{Path, PathBuf};
use std::time::Duration;

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Engine {
    /// Combustion engine, also used for electric locos.
    Diesel,
    Steam,
}

/// The sounds of the engine outside the segments: a combustion engine
/// starts, idles and quits (B-12); a steam engine idles and blows off
/// steam from the cylinders when it starts moving (B-14).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EngineSound {
    Start,
    Idle,
    Quit,
    Cylinder,
}

/// The sounds of a segment of a combustion engine (B-11): `load` and
/// `idle` loop while the speed stays in the segment after accelerating or
/// braking, `accel` leads into the segment from below and `decel` out of
/// it downwards.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SegmentSound {
    Load,
    Idle,
    Accel,
    Decel,
}

/// Sound files on the host by their use.
pub type Sounds<K> = BTreeMap<K, PathBuf>;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SoundModel {
    engine: Engine,
    #[serde(default)]
    sounds: Sounds<EngineSound>,
    /// Sorted by speed; the first starts at standstill.
    segments: Vec<Segment>,
    #[serde(default)]
    steam: Steam,
}

/// How a steam engine strokes (B-14), with the defaults of Electrip 1.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Steam {
    /// Cylinder strokes per turn of the driving wheels.
    pub strokes: usize,
    /// Diameter of the driving wheels in m.
    pub wheel_diameter: f64,
    /// Seconds from blowing off steam to the first stroke.
    pub start_delay: f64,
    /// The fewest strokes per second, so the pauses stay short when the
    /// loco creeps.
    pub min_frequency: f64,
}

/// Allowed values of [`Steam`], as in Electrip 1 where it does not crash.
const STROKES_RANGE: RangeInclusive<usize> = 1..=9999;
const WHEEL_DIAMETER_RANGE: RangeInclusive<f64> = 0.1..=99.0;
const START_DELAY_RANGE: RangeInclusive<f64> = 0.0..=9999.0;
const MIN_FREQUENCY_RANGE: RangeInclusive<f64> = 0.1..=9999.0;

impl Default for Steam {
    fn default() -> Self {
        Steam {
            strokes: 4,
            wheel_diameter: 1.2,
            start_delay: 2.0,
            min_frequency: 0.2,
        }
    }
}

impl Steam {
    fn is_valid(&self) -> bool {
        STROKES_RANGE.contains(&self.strokes)
            && WHEEL_DIAMETER_RANGE.contains(&self.wheel_diameter)
            && START_DELAY_RANGE.contains(&self.start_delay)
            && MIN_FREQUENCY_RANGE.contains(&self.min_frequency)
    }

    /// The pause between two strokes at `speed` (km/h, above standstill):
    /// one turn of the wheels split into the strokes, at most the pause of
    /// the minimum frequency. Values out of range, which only a broken file
    /// brings, give none.
    pub fn pause(&self, speed: f64) -> Option<Duration> {
        if !self.is_valid() {
            return None;
        }
        let turn = 3.6 * self.wheel_diameter * PI / speed;
        let pause = (turn / self.strokes as f64).min(1.0 / self.min_frequency);
        Some(Duration::from_secs_f64(pause))
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Segment {
    /// Speed in km/h where the segment begins; it ends where the next one
    /// begins, the last one at Vmax.
    pub start: f64,
    #[serde(default)]
    pub sounds: Sounds<SegmentSound>,
    /// The sounds of the cylinder strokes of a steam engine by number.
    #[serde(default)]
    pub strokes: Sounds<usize>,
}

impl SoundModel {
    pub fn new(engine: Engine) -> Self {
        SoundModel::with(engine, Sounds::new(), Vec::new())
    }

    /// A model with the given sounds and segments; the first segment
    /// begins at standstill, without segments there is one.
    pub fn with(engine: Engine, sounds: Sounds<EngineSound>, mut segments: Vec<Segment>) -> Self {
        match segments.first_mut() {
            Some(first) => first.start = 0.0,
            None => segments.push(Segment::default()),
        }
        SoundModel {
            engine,
            sounds,
            segments,
            steam: Steam::default(),
        }
    }

    pub fn engine(&self) -> Engine {
        self.engine
    }

    pub fn segments(&self) -> &[Segment] {
        &self.segments
    }

    pub fn sound(&self, sound: EngineSound) -> Option<&Path> {
        self.sounds.get(&sound).map(PathBuf::as_path)
    }

    /// The sound of the `nr`-th segment, none if there is no such segment.
    pub fn segment_sound(&self, nr: usize, sound: SegmentSound) -> Option<&Path> {
        let segment = self.segments.get(nr)?;
        segment.sounds.get(&sound).map(PathBuf::as_path)
    }

    /// The sound of the `stroke`-th cylinder stroke in the `nr`-th segment.
    pub fn stroke_sound(&self, nr: usize, stroke: usize) -> Option<&Path> {
        let segment = self.segments.get(nr)?;
        segment.strokes.get(&stroke).map(PathBuf::as_path)
    }

    pub fn steam(&self) -> &Steam {
        &self.steam
    }

    pub(crate) fn set_steam(&mut self, steam: Steam) -> Result<(), LocoError> {
        if !steam.is_valid() {
            return Err(LocoError::SteamOutOfRange);
        }
        self.steam = steam;
        Ok(())
    }

    /// The number of segments that begin below `speed`: 0 at standstill,
    /// else the segment of the speed counted from 1.
    pub fn level(&self, speed: f64) -> usize {
        self.segments.iter().filter(|s| s.start < speed).count()
    }

    /// Sets the sound file or with `None` removes it.
    pub(crate) fn set_sound(&mut self, sound: EngineSound, path: Option<PathBuf>) {
        set(&mut self.sounds, sound, path);
    }

    pub(crate) fn set_segment_sound(
        &mut self,
        nr: usize,
        sound: SegmentSound,
        path: Option<PathBuf>,
    ) -> Result<(), LocoError> {
        self.check(nr)?;
        set(&mut self.segments[nr].sounds, sound, path);
        Ok(())
    }

    pub(crate) fn set_stroke_sound(
        &mut self,
        nr: usize,
        stroke: usize,
        path: Option<PathBuf>,
    ) -> Result<(), LocoError> {
        self.check(nr)?;
        if stroke >= self.steam.strokes {
            return Err(LocoError::UnknownStroke(stroke));
        }
        set(&mut self.segments[nr].strokes, stroke, path);
        Ok(())
    }

    /// Splits the `nr`-th segment in the middle like Electrip 1; the new
    /// segment is the right half.
    pub(crate) fn insert_segment(&mut self, nr: usize, max_speed: f64) -> Result<(), LocoError> {
        self.check(nr)?;
        let end = self.segments.get(nr + 1).map_or(max_speed, |s| s.start);
        let start = 0.5 * (self.segments[nr].start + end);
        let segment = Segment {
            start,
            ..Segment::default()
        };
        self.segments.insert(nr + 1, segment);
        Ok(())
    }

    /// Removes the `nr`-th segment; its left neighbour, for the first
    /// segment its right one, takes over its speeds. The caller removes the
    /// whole model instead of its only segment.
    pub(crate) fn remove_segment(&mut self, nr: usize) -> Result<(), LocoError> {
        self.check(nr)?;
        self.segments.remove(nr);
        if let Some(first) = self.segments.first_mut() {
            first.start = 0.0;
        }
        Ok(())
    }

    /// Moves the border where the `nr`-th segment begins to `speed`. The
    /// first segment always begins at standstill, and a border only moves
    /// between its neighbours; other speeds are ignored like for the points
    /// of the speed curve.
    pub(crate) fn move_border(
        &mut self,
        nr: usize,
        speed: f64,
        max_speed: f64,
    ) -> Result<(), LocoError> {
        self.check(nr)?;
        let left = nr.checked_sub(1).map(|i| self.segments[i].start);
        let right = self.segments.get(nr + 1).map_or(max_speed, |s| s.start);
        if left.is_some_and(|left| left < speed && speed < right) {
            self.segments[nr].start = speed;
        }
        Ok(())
    }

    /// Stretches the segments to a new Vmax.
    pub(crate) fn scale(&mut self, factor: f64) {
        for segment in &mut self.segments {
            segment.start *= factor;
        }
    }

    /// An error if there is no `nr`-th segment.
    pub(crate) fn check(&self, nr: usize) -> Result<(), LocoError> {
        if nr < self.segments.len() {
            Ok(())
        } else {
            Err(LocoError::UnknownSegment(nr))
        }
    }
}

fn set<K: Ord>(sounds: &mut Sounds<K>, sound: K, path: Option<PathBuf>) {
    match path {
        Some(path) => sounds.insert(sound, path),
        None => sounds.remove(&sound),
    };
}

#[cfg(test)]
mod tests;
