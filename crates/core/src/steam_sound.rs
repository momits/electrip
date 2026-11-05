//! The driving sound of a steam engine (B-14) as Electrip 1 plays it
//! (`SteamSoundController` in `legacy/src/electrip/pygame_io.py`). While
//! the engine runs, its idle sound loops. While the loco moves, the
//! cylinder strokes follow each other with a pause from speed and wheel
//! (see [`Steam::pause`](crate::sound::Steam::pause)), each stroke on its
//! own channel so they may overlap. Starting to move blows off steam
//! first and strokes after the start delay, unless the steam still blows.
//!
//! The host polls; a stroke due before the next poll is sent with its
//! delay. The pause between strokes comes from the speed at the poll
//! before, as Electrip 1 takes the speed at the stroke before.

use crate::audio::{AudioSink, Channel, ChannelId};
use crate::sound::{EngineSound, SoundModel};
use std::time::Duration;

/// The channels of a loco: 0 idle, 1 steam, then one per stroke.
const FIRST_STROKE_CHANNEL: usize = 2;

#[derive(Debug, Clone, Default, PartialEq)]
pub(crate) struct SteamSound {
    loco: u32,
    idle: Channel,
    cylinder: Channel,
    /// The number of strokes per turn while the engine runs; 0 when off.
    strokes: usize,
    /// The stroke that comes next.
    stroke: usize,
    /// Time from the last poll to the next stroke not yet sent; none while
    /// the loco stands.
    next: Option<Duration>,
}

impl SteamSound {
    pub(crate) fn new(loco: u32) -> Self {
        let channel = |nr| Channel::new(ChannelId { loco, nr });
        SteamSound {
            loco,
            idle: channel(0),
            cylinder: channel(1),
            ..SteamSound::default()
        }
    }

    pub(crate) fn is_running(&self) -> bool {
        self.strokes > 0
    }

    /// Starts the idle sound; when the loco moves, the strokes start at
    /// the next poll without blowing off steam.
    pub(crate) fn start(&mut self, model: &SoundModel, speed: f64, sink: &mut dyn AudioSink) {
        self.strokes = model.steam().strokes;
        self.stroke = 0;
        let idle = model.sound(EngineSound::Idle);
        self.idle.queue(sink, idle);
        self.idle.queue(sink, idle);
        self.next = (speed > 0.0).then_some(Duration::ZERO);
    }

    /// Silences every channel at once.
    pub(crate) fn stop(&mut self, sink: &mut dyn AudioSink) {
        self.idle.stop(sink);
        self.cylinder.stop(sink);
        for stroke in 0..self.strokes {
            sink.stop(self.stroke_channel(stroke));
        }
        self.strokes = 0;
        self.next = None;
    }

    /// Lets `elapsed` pass at `speed` and sends the strokes due before the
    /// next poll, assuming it comes after `elapsed` again.
    pub(crate) fn play(
        &mut self,
        model: &SoundModel,
        speed: f64,
        sink: &mut dyn AudioSink,
        elapsed: Duration,
    ) {
        let mut rest = elapsed;
        while self.idle.advance(&mut rest) {
            self.idle.queue(sink, model.sound(EngineSound::Idle));
        }
        self.cylinder.advance(&mut elapsed.clone());
        if speed == 0.0 {
            self.next = None;
            return;
        }
        let mut next = match self.next {
            Some(next) => next.saturating_sub(elapsed),
            None if self.cylinder.is_silent() => {
                self.cylinder
                    .queue(sink, model.sound(EngineSound::Cylinder));
                Duration::from_secs_f64(model.steam().start_delay)
            }
            None => Duration::ZERO,
        };
        let segment = model.level(speed) - 1;
        while next <= elapsed {
            if let Some(sound) = model.stroke_sound(segment, self.stroke) {
                sink.play(self.stroke_channel(self.stroke), sound, next);
            }
            self.stroke = (self.stroke + 1) % self.strokes;
            next += model.steam().pause(speed);
        }
        self.next = Some(next);
    }

    fn stroke_channel(&self, stroke: usize) -> ChannelId {
        ChannelId {
            loco: self.loco,
            nr: FIRST_STROKE_CHANNEL + stroke,
        }
    }
}

#[cfg(test)]
mod tests;
