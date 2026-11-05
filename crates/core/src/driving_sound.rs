//! The driving sound of a combustion engine (B-11, B-12) as Electrip 1
//! plays it (`DieselSoundController` in `legacy/src/electrip/pygame_io.py`).
//! The channel always holds the next sound, so the engine follows a new
//! speed only after the current and the waiting sound. It climbs and falls
//! one segment per sound: the accel sound leads into the next segment, the
//! decel sound out of the current one, and in between the load sound loops
//! after accelerating, the idle sound after braking.
//!
//! Starting plays the start sound and stops at the idle sound; switching
//! off at standstill waits for the idle sound and then plays the quit
//! sound. Meanwhile the speed is locked. Switching on while driving starts
//! with the load sound, switching off while driving silences at once.
//!
//! The loco follows the sound (B-13): it starts only when the sound leading
//! into the first segment begins and stops only when the sound leading out
//! of it begins.

use crate::audio::{AudioSink, Channel};
use crate::sound::{Engine, EngineSound, SegmentSound, SoundModel};
use crate::station::LocoState;
use serde::Serialize;
use std::cmp::Ordering;
use std::time::Duration;

#[derive(Debug, Clone, Copy, Default, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SoundState {
    #[default]
    Off,
    Starting,
    On,
    Stopping,
}

/// Seen from outside only its state.
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
#[serde(into = "SoundState")]
pub struct DrivingSound {
    state: SoundState,
    channel: Channel,
    /// Where the queued sounds lead: 0 is standstill, n the n-th segment.
    level: usize,
    /// Where the playing sound leads.
    audible: usize,
    /// Whether the engine reached the level accelerating.
    on_load: bool,
    /// Whether the quit sound is queued; the sound ends with it.
    quitting: bool,
}

impl From<DrivingSound> for SoundState {
    fn from(sound: DrivingSound) -> Self {
        sound.state
    }
}

impl DrivingSound {
    /// The sound of the loco with this id; it plays on the channel of the
    /// same number.
    pub(crate) fn new(id: u32) -> Self {
        DrivingSound {
            channel: Channel::new(id),
            ..DrivingSound::default()
        }
    }

    pub fn state(&self) -> SoundState {
        self.state
    }

    /// Whether the speed stays as it is while the engine starts or stops.
    pub fn locks_speed(&self) -> bool {
        matches!(self.state, SoundState::Starting | SoundState::Stopping)
    }

    /// What the command station gets instead of `state` after `last`
    /// while the sound plays: standstill until the sound leaves the idle,
    /// and the last step and direction until it returns there.
    pub fn synchronize(&self, mut state: LocoState, last: &LocoState) -> LocoState {
        if self.state == SoundState::Off {
            return state;
        }
        if self.audible == 0 {
            state.step = 0;
        } else if state.step == 0 {
            state.step = last.step;
            state.forward = last.forward;
        }
        state
    }

    /// The sound switch. Only combustion engines have a driving sound yet;
    /// steam comes with B-14. Without a sound to play it stays off.
    pub(crate) fn toggle(
        &mut self,
        model: Option<&SoundModel>,
        speed: f64,
        sink: &mut dyn AudioSink,
    ) {
        let Some(model) = model.filter(|m| m.engine() == Engine::Diesel) else {
            return;
        };
        let standstill = speed == 0.0;
        match self.state {
            SoundState::Off if standstill => {
                self.state = SoundState::Starting;
                self.level = 0;
                self.audible = 0;
                self.quitting = false;
                self.channel.queue(sink, model.sound(EngineSound::Start));
                self.channel.queue(sink, model.sound(EngineSound::Idle));
            }
            SoundState::Off => {
                self.state = SoundState::On;
                self.level = model.level(speed);
                self.audible = self.level;
                self.on_load = true;
                self.quitting = false;
                self.update(model, speed, sink);
                self.update(model, speed, sink);
            }
            SoundState::On if standstill => self.state = SoundState::Stopping,
            SoundState::On => self.channel.stop(sink),
            SoundState::Starting | SoundState::Stopping => {}
        }
        self.off_if_silent();
    }

    /// Lets `elapsed` pass at `speed`; each sound that ends is followed by
    /// the next. Without a model the sound stops.
    pub(crate) fn play(
        &mut self,
        model: Option<&SoundModel>,
        speed: f64,
        sink: &mut dyn AudioSink,
        mut elapsed: Duration,
    ) {
        if self.state == SoundState::Off {
            return;
        }
        let Some(model) = model else {
            self.channel.stop(sink);
            self.state = SoundState::Off;
            return;
        };
        while self.channel.advance(&mut elapsed) {
            self.audible = self.level;
            self.update(model, speed, sink);
        }
        self.off_if_silent();
    }

    /// Queues the sound that leads one segment towards `speed` or loops in
    /// it (`update_engine_queue` in Electrip 1).
    fn update(&mut self, model: &SoundModel, speed: f64, sink: &mut dyn AudioSink) {
        if self.quitting {
            return;
        }
        let target = model.level(speed);
        let idle = self.level == 0 && target == 0;
        let sound = match self.level.cmp(&target) {
            Ordering::Less => {
                self.level += 1;
                self.on_load = true;
                model.segment_sound(self.level - 1, SegmentSound::Accel)
            }
            Ordering::Equal if idle => model.sound(EngineSound::Idle),
            Ordering::Equal if self.on_load => {
                model.segment_sound(self.level - 1, SegmentSound::Load)
            }
            Ordering::Equal => model.segment_sound(self.level - 1, SegmentSound::Idle),
            Ordering::Greater => {
                self.level -= 1;
                self.on_load = false;
                model.segment_sound(self.level, SegmentSound::Decel)
            }
        };
        self.channel.queue(sink, sound);
        if idle {
            self.reached_idle(model, sink);
        }
    }

    /// Ends starting, or begins quitting after switching off.
    fn reached_idle(&mut self, model: &SoundModel, sink: &mut dyn AudioSink) {
        match self.state {
            SoundState::Starting => self.state = SoundState::On,
            SoundState::Stopping => {
                self.quitting = true;
                self.channel.queue(sink, model.sound(EngineSound::Quit));
            }
            SoundState::Off | SoundState::On => {}
        }
    }

    fn off_if_silent(&mut self) {
        if self.channel.is_silent() {
            self.state = SoundState::Off;
        }
    }
}

#[cfg(test)]
mod tests;
