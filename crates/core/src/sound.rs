//! The sound model of a loco (B-15): a combustion or steam engine whose
//! speed range from standstill to Vmax is split into segments, each with
//! its own sounds. Like in Electrip 1 a new model has one segment over the
//! whole range.

use crate::loco::LocoError;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Engine {
    /// Combustion engine, also used for electric locos.
    Diesel,
    Steam,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SoundModel {
    engine: Engine,
    /// Sorted by speed; the first starts at standstill.
    segments: Vec<Segment>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Segment {
    /// Speed in km/h where the segment begins; it ends where the next one
    /// begins, the last one at Vmax.
    pub start: f64,
}

impl SoundModel {
    pub fn new(engine: Engine) -> Self {
        SoundModel {
            engine,
            segments: vec![Segment { start: 0.0 }],
        }
    }

    pub fn engine(&self) -> Engine {
        self.engine
    }

    pub fn segments(&self) -> &[Segment] {
        &self.segments
    }

    /// Splits the `nr`-th segment in the middle like Electrip 1; the new
    /// segment is the right half.
    pub(crate) fn insert_segment(&mut self, nr: usize, max_speed: f64) -> Result<(), LocoError> {
        self.check(nr)?;
        let end = self.segments.get(nr + 1).map_or(max_speed, |s| s.start);
        let start = 0.5 * (self.segments[nr].start + end);
        self.segments.insert(nr + 1, Segment { start });
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

#[cfg(test)]
mod tests;
