//! Speed curve of a loco: maps the displayed speed in km/h to a decoder speed
//! step through linear segments between control points (B-08).
//!
//! The curve rises monotonically. Like in Electrip 1, the first point (start
//! step) and the last point (step at Vmax) always exist and keep their speed.

use serde::{Deserialize, Serialize};

pub type Point = (f64, f64);

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(transparent)]
pub struct SpeedCurve {
    points: Vec<Point>,
}

impl SpeedCurve {
    /// Builds the curve like Electrip 1: the first and last point span it,
    /// the inner points are added in order with [`SpeedCurve::add_point`].
    /// `None` if there are fewer than two points or the ends span no speed.
    pub fn new(points: &[Point]) -> Option<Self> {
        let (&first, &last) = (points.first()?, points.last()?);
        if first.0 >= last.0 {
            return None;
        }
        let mut curve = SpeedCurve {
            points: vec![first, last],
        };
        for &(speed, step) in &points[1..points.len() - 1] {
            curve.add_point(speed, step);
        }
        Some(curve)
    }

    /// The straight curve from step 0 at standstill to `max_steps` at
    /// `max_speed`, as Electrip 1 sets it on a reset. `max_speed` must be
    /// above 0.
    pub(crate) fn straight(max_speed: f64, max_steps: f64) -> Self {
        SpeedCurve {
            points: vec![(0.0, 0.0), (max_speed, max_steps)],
        }
    }

    pub fn points(&self) -> &[Point] {
        &self.points
    }

    /// Adds a point inside the curve. Its step is limited to the steps of the
    /// neighbours, so the curve keeps rising. Points on an existing speed or
    /// outside the curve are ignored.
    pub fn add_point(&mut self, speed: f64, step: f64) {
        let Some(nr) = self
            .points
            .windows(2)
            .position(|w| w[0].0 < speed && speed < w[1].0)
        else {
            return;
        };
        let step = step.min(self.points[nr + 1].1).max(self.points[nr].1);
        self.points.insert(nr + 1, (speed, step));
    }

    /// Removes the `nr`-th point; the first and last point stay.
    pub fn remove_point(&mut self, nr: usize) {
        if nr != 0 && nr + 1 < self.points.len() {
            self.points.remove(nr);
        }
    }

    /// Moves the `nr`-th point like Electrip 1: the ends only change their
    /// step, an inner point only moves between its neighbours' speeds, and
    /// every step is limited to the steps of the neighbours.
    pub fn move_point(&mut self, nr: usize, speed: f64, step: f64) {
        let Some(&(old_speed, _)) = self.points.get(nr) else {
            return;
        };
        let left = nr.checked_sub(1).and_then(|i| self.points.get(i)).copied();
        let right = self.points.get(nr + 1).copied();
        let speed = match (left, right) {
            (Some(l), Some(r)) if l.0 < speed && speed < r.0 => speed,
            (Some(_), Some(_)) => return,
            _ => old_speed,
        };
        let step = left.map_or(step, |l| step.max(l.1));
        let step = right.map_or(step, |r| step.min(r.1));
        self.points[nr] = (speed, step);
    }

    /// The speed step at `speed`, not yet rounded; speed 0 is always step 0.
    /// `None` outside the curve.
    pub fn step_at(&self, speed: f64) -> Option<f64> {
        if speed == 0.0 {
            return Some(0.0);
        }
        let w = self
            .points
            .windows(2)
            .find(|w| w[0].0 <= speed && speed <= w[1].0)?;
        // Same formula and order of operations as Electrip 1, so the golden
        // test matches bit for bit.
        let ((x1, y1), (x2, y2)) = (w[0], w[1]);
        let a = (y2 - y1) / (x2 - x1);
        let b = y2 - x2 * a;
        Some(a * speed + b)
    }

    /// The speed in the middle of `step`, so that [`SpeedCurve::step_at`]
    /// cuts off to `step` again; 0 for step 0, Vmax above the curve.
    pub fn speed_of_step(&self, step: u8) -> f64 {
        if step == 0 {
            return 0.0;
        }
        let step = f64::from(step) + 0.5;
        let rising = |w: &&[Point]| w[0].1 < w[1].1 && step <= w[1].1;
        match self.points.windows(2).find(rising) {
            Some(w) => {
                let ((x1, y1), (x2, y2)) = (w[0], w[1]);
                x1 + (step - y1).max(0.0) * (x2 - x1) / (y2 - y1)
            }
            None => self.points.last().map_or(0.0, |p| p.0),
        }
    }
}

#[cfg(test)]
mod tests;
