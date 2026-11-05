//! The sound model of a loco (B-15): a combustion or steam engine whose
//! speed range from standstill to Vmax is split into segments, each with
//! its own sounds. Like in Electrip 1 a new model has one segment over the
//! whole range.

use crate::loco::LocoError;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Engine {
    /// Combustion engine, also used for electric locos.
    Diesel,
    Steam,
}

/// The sounds of a combustion engine at standstill (B-12).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EngineSound {
    Start,
    Idle,
    Quit,
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
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Segment {
    /// Speed in km/h where the segment begins; it ends where the next one
    /// begins, the last one at Vmax.
    pub start: f64,
    #[serde(default)]
    pub sounds: Sounds<SegmentSound>,
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
