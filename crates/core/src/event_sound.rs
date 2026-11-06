//! Event sounds (B-17): sounds that play while the loco drives in a given
//! way, such as squealing brakes, as Electrip 1 plays them
//! (`EventSoundPlayer` in `legacy/src/electrip/pygame_io.py`). Each plays
//! on its own channel above the driving sound and loops while its
//! conditions hold.
//!
//! Unlike Electrip 1 (Q-013) the host checks the conditions at each poll
//! with the current values: the acceleration is the change of speed since
//! the last poll, and a bound of 0 or a backward direction counts.

use crate::audio::{AudioSink, Channel, ChannelId};
use crate::drive::Motion;
use crate::steam_sound;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::time::Duration;

/// A sound file `path` on the host and when it plays; bounds that are
/// `null` hold always.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct EventSound {
    /// Switches it active and inactive.
    pub action: u32,
    #[serde(default)]
    pub name: String,
    pub path: Option<PathBuf>,
    /// Whether it is active at the start.
    #[serde(default = "default_active")]
    pub default_active: bool,
    /// Whether it is active now; only then it plays.
    #[serde(default)]
    pub active: bool,
    /// Only forward (`true`) or only backward (`false`).
    pub forward: Option<bool>,
    /// Bounds of the speed in km/h.
    pub min_speed: Option<f64>,
    pub max_speed: Option<f64>,
    /// Bounds of the acceleration in km/h per second.
    pub min_accel: Option<f64>,
    pub max_accel: Option<f64>,
    /// Seconds to rise from silence at the start.
    #[serde(default)]
    pub fade_in: f64,
    /// Seconds to fall silent when the conditions stop holding.
    #[serde(default)]
    pub fade_out: f64,
    /// Once started, it plays to its end without fading out.
    #[serde(default)]
    pub play_to_end: bool,
    #[serde(skip)]
    pub(crate) channel: Channel,
    #[serde(skip)]
    pub(crate) fading: bool,
}

/// Like Electrip 1.
pub(crate) fn default_active() -> bool {
    true
}

impl EventSound {
    /// The same event sound, silent and as active as at the start.
    pub(crate) fn reset(&self) -> Self {
        EventSound {
            active: self.default_active,
            channel: Channel::default(),
            fading: false,
            ..self.clone()
        }
    }

    /// Whether it plays for a loco in `motion` with `accel`.
    fn holds(&self, motion: &Motion, accel: f64) -> bool {
        let within = |value: f64, min: Option<f64>, max: Option<f64>| {
            min.is_none_or(|min| value >= min) && max.is_none_or(|max| value <= max)
        };
        self.active
            && self.forward.is_none_or(|f| f == motion.forward())
            && within(motion.speed(), self.min_speed, self.max_speed)
            && within(accel, self.min_accel, self.max_accel)
    }

    /// Lets `elapsed` pass, then starts the silent sound if it holds or
    /// fades it out if it no longer does.
    fn play(
        &mut self,
        holds: bool,
        channel: ChannelId,
        sink: &mut dyn AudioSink,
        elapsed: Duration,
    ) {
        let mut elapsed = elapsed;
        while self.channel.advance(&mut elapsed) {}
        if self.channel.is_silent() {
            self.fading = false;
            if holds {
                self.channel = Channel::new(channel);
                let fade = seconds(self.fade_in);
                self.channel.fade_in(sink, self.path.as_deref(), fade);
            }
        } else if !holds && !self.play_to_end && !self.fading {
            self.fading = true;
            self.channel.fade_out(sink, seconds(self.fade_out));
        }
    }
}

/// The channel number of the `index`-th event sound of a loco; sound
/// functions play above the last.
pub(crate) fn channel_nr(index: usize) -> usize {
    steam_sound::CHANNELS + index
}

/// Plays the event sounds of the loco `loco` for `elapsed`, while it moves
/// as `motion` with `accel` in km/h per second; with `None`, as without a
/// driving sound, none holds.
pub(crate) fn play(
    sounds: &mut [EventSound],
    loco: u32,
    motion: Option<(Motion, f64)>,
    sink: &mut dyn AudioSink,
    elapsed: Duration,
) {
    for (index, sound) in sounds.iter_mut().enumerate() {
        let holds = motion.is_some_and(|(motion, accel)| sound.holds(&motion, accel));
        let channel = ChannelId {
            loco,
            nr: channel_nr(index),
        };
        sound.play(holds, channel, sink, elapsed);
    }
}

fn seconds(seconds: f64) -> Duration {
    Duration::try_from_secs_f64(seconds).unwrap_or_default()
}

#[cfg(test)]
mod tests;
