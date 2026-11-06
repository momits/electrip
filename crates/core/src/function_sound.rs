//! Sound functions (B-16): sounds that an action switches like a decoder
//! function, as Electrip 1 plays them (`FunctionSoundPlayer` in
//! `legacy/src/electrip/pygame_io.py`). Each plays on its own channel.

use crate::audio::{AudioSink, Channel, ChannelId};
use crate::steam_sound;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::time::Duration;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SoundMode {
    /// The first trigger starts the loop, the second stops it.
    Switch,
    /// Plays at most once while the action is held.
    PushOnce,
    /// Loops while the action is held.
    Push,
    /// Plays to the end; triggers meanwhile do nothing.
    #[default]
    Tap,
}

/// A sound file `path` on the host that the action `action` plays.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct SoundFunction {
    pub action: u32,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub mode: SoundMode,
    pub path: Option<PathBuf>,
    /// Whether it is on now; off at the start.
    #[serde(default)]
    pub on: bool,
    #[serde(skip)]
    pub(crate) channel: Channel,
}

impl SoundFunction {
    /// The same function, off and silent.
    pub(crate) fn off(&self) -> Self {
        SoundFunction {
            on: false,
            channel: Channel::default(),
            ..self.clone()
        }
    }

    /// Reacts to pressing (`pressed`) or releasing the action; a sound
    /// that starts plays on `channel`.
    fn trigger(&mut self, pressed: bool, channel: ChannelId, sink: &mut dyn AudioSink) {
        let on = match self.mode {
            SoundMode::Switch => self.on ^ pressed,
            SoundMode::PushOnce | SoundMode::Push => pressed,
            SoundMode::Tap => self.on || pressed,
        };
        if on == self.on {
            return;
        }
        self.on = on;
        if !on {
            self.channel.stop(sink);
            return;
        }
        self.channel = Channel::new(channel);
        self.channel.queue(sink, self.path.as_deref());
        if self.loops() {
            self.channel.queue(sink, self.path.as_deref());
        }
    }

    /// Lets `elapsed` pass; a loop queues its sound again after each end,
    /// a tapped sound switches off at its end. Returns whether it switched
    /// off.
    pub(crate) fn play(&mut self, sink: &mut dyn AudioSink, mut elapsed: Duration) -> bool {
        while self.channel.advance(&mut elapsed) {
            if self.loops() {
                self.channel.queue(sink, self.path.as_deref());
            }
        }
        let ended = self.on && self.mode == SoundMode::Tap && self.channel.is_silent();
        self.on &= !ended;
        ended
    }

    fn loops(&self) -> bool {
        matches!(self.mode, SoundMode::Switch | SoundMode::Push)
    }
}

/// Triggers the sound functions of the loco `loco` mapped to `action`.
pub(crate) fn trigger(
    functions: &mut [SoundFunction],
    loco: u32,
    action: u32,
    pressed: bool,
    sink: &mut dyn AudioSink,
) {
    for index in 0..functions.len() {
        if functions[index].action == action {
            let nr = free_channel(functions);
            functions[index].trigger(pressed, ChannelId { loco, nr }, sink);
        }
    }
}

/// The first channel after the driving sound where no sound function plays.
fn free_channel(functions: &[SoundFunction]) -> usize {
    let busy: Vec<usize> = functions
        .iter()
        .filter(|f| !f.channel.is_silent())
        .map(|f| f.channel.id().nr)
        .collect();
    let mut nr = steam_sound::CHANNELS;
    while busy.contains(&nr) {
        nr += 1;
    }
    nr
}

#[cfg(test)]
mod tests;
