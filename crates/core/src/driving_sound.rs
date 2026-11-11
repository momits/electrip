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
//!
//! A steam engine plays as [`SteamSound`]; it is on or off.
//!
//! The sound level shows where the sound stands for the fill level of the
//! speed scale (B-22, `animate_fill_level` in
//! `legacy/src/electrip/control_ui.py`): while a sound plays that leads
//! to another segment, it moves evenly to the end of that segment; a
//! steam engine follows the speed.

use crate::audio::{AudioSink, Channel, ChannelId};
use crate::sound::{Engine, EngineSound, SegmentSound, SoundModel};
use crate::station::LocoState;
use crate::steam_sound::SteamSound;
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

/// Seen from outside only its state and level.
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
#[serde(into = "SoundView")]
pub struct DrivingSound {
    state: SoundState,
    /// The sound level in km/h; 0 while off.
    sound_level: f64,
    channel: Channel,
    /// Where the queued sounds lead: 0 is standstill, n the n-th segment.
    level: usize,
    /// Where the playing sound leads.
    audible: usize,
    /// Whether the engine reached the level accelerating.
    on_load: bool,
    /// Whether the quit sound is queued; the sound ends with it.
    quitting: bool,
    steam: SteamSound,
}

#[derive(Serialize)]
struct SoundView {
    sound: SoundState,
    sound_level: f64,
}

impl From<DrivingSound> for SoundView {
    fn from(sound: DrivingSound) -> Self {
        SoundView {
            sound: sound.state,
            sound_level: sound.sound_level,
        }
    }
}

impl DrivingSound {
    /// The sound of the loco with this id; it plays on the channel of the
    /// same number.
    pub(crate) fn new(id: u32) -> Self {
        DrivingSound {
            channel: Channel::new(ChannelId { loco: id, nr: 0 }),
            steam: SteamSound::new(id),
            ..DrivingSound::default()
        }
    }

    pub fn state(&self) -> SoundState {
        self.state
    }

    pub fn sound_level(&self) -> f64 {
        self.sound_level
    }

    /// Whether the speed stays as it is while the engine starts or stops.
    pub fn locks_speed(&self) -> bool {
        matches!(self.state, SoundState::Starting | SoundState::Stopping)
    }

    /// What the command station gets instead of `state` after `last`
    /// while the sound plays: standstill until the sound leaves the idle,
    /// and the last step and direction until it returns there.
    pub(crate) fn synchronize(&self, mut state: LocoState, last: &LocoState) -> LocoState {
        if self.state == SoundState::Off || self.steam.is_running() {
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

    /// The sound switch. A combustion engine without a sound to play stays
    /// off.
    pub(crate) fn toggle(
        &mut self,
        model: Option<&SoundModel>,
        speed: f64,
        max_speed: f64,
        sink: &mut dyn AudioSink,
    ) {
        let Some(model) = model else {
            return;
        };
        if model.engine() == Engine::Steam {
            self.toggle_steam(model, speed, sink);
            return;
        }
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
                self.sound_level = model.level_end(self.level, max_speed);
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

    fn toggle_steam(&mut self, model: &SoundModel, speed: f64, sink: &mut dyn AudioSink) {
        if self.state == SoundState::Off {
            self.steam.start(model, speed, sink);
            self.state = SoundState::On;
            self.sound_level = speed;
        } else {
            self.stop(sink);
        }
    }

    /// Lets `elapsed` pass at `speed`; each sound that ends is followed by
    /// the next. Without a model or with one of another engine the sound
    /// stops.
    pub(crate) fn play(
        &mut self,
        model: Option<&SoundModel>,
        speed: f64,
        max_speed: f64,
        sink: &mut dyn AudioSink,
        mut elapsed: Duration,
    ) {
        if self.state == SoundState::Off {
            return;
        }
        let steam = self.steam.is_running();
        let Some(model) = model.filter(|m| (m.engine() == Engine::Steam) == steam) else {
            self.stop(sink);
            return;
        };
        if steam {
            self.steam.play(model, speed, sink, elapsed);
            self.sound_level = speed;
            return;
        }
        loop {
            let end = model.level_end(self.audible, max_speed);
            let (rest, before) = (self.channel.remaining(), elapsed);
            let ended = self.channel.advance(&mut elapsed);
            self.move_level(end, rest, before - elapsed);
            if !ended {
                break;
            }
            self.audible = self.level;
            self.update(model, speed, sink);
        }
        self.off_if_silent();
    }

    /// Moves the level evenly so it reaches `end` when the sound that
    /// played `rest` before ends; `passed` of it has passed.
    fn move_level(&mut self, end: f64, rest: Option<Duration>, passed: Duration) {
        let Some(rest) = rest else {
            return;
        };
        let part = (passed.as_secs_f64() / rest.as_secs_f64()).min(1.0);
        self.sound_level += (end - self.sound_level) * part;
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

    fn stop(&mut self, sink: &mut dyn AudioSink) {
        if self.steam.is_running() {
            self.steam.stop(sink);
        } else {
            self.channel.stop(sink);
        }
        self.state = SoundState::Off;
        self.sound_level = 0.0;
    }

    fn off_if_silent(&mut self) {
        if self.channel.is_silent() {
            self.state = SoundState::Off;
            self.sound_level = 0.0;
        }
    }
}

#[cfg(test)]
mod tests;
