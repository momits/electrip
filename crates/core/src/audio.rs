//! The audio target of the locos (ADR 0004). The session host runs the sound
//! models and sends their sounds to the target; it reckons with the length
//! of the files, not with the playback (B-13).

use std::path::Path;
use std::time::Duration;

pub type Audio = Box<dyn AudioSink + Send>;

/// A channel of the audio target: the loco and its `nr`-th channel. The
/// driving sound plays on channel 0, a steam engine also on the following.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct ChannelId {
    pub loco: u32,
    pub nr: usize,
}

/// Plays the sounds of the locos, each loco on its own channels.
pub trait AudioSink {
    /// The length of a sound file.
    fn length(&mut self, sound: &Path) -> Result<Duration, String>;

    /// Plays the sound on the channel: at once if the channel is silent,
    /// else without a gap after the current sound. It replaces a sound
    /// that waits there.
    fn queue(&mut self, channel: ChannelId, sound: &Path);

    /// Plays the sound on the channel after `delay`; it cuts off what plays
    /// there then. Sounds the target cannot read are left out.
    fn play(&mut self, channel: ChannelId, sound: &Path, delay: Duration);

    /// Silences the channel and drops its waiting sound.
    fn stop(&mut self, channel: ChannelId);
}

/// What the host knows of a channel of the audio target: how long its
/// sound still plays and how long the waiting one lasts.
#[derive(Debug, Clone, Default, PartialEq)]
pub(crate) struct Channel {
    id: ChannelId,
    playing: Option<Duration>,
    waiting: Option<Duration>,
}

impl Channel {
    pub(crate) fn new(id: ChannelId) -> Self {
        Channel {
            id,
            ..Channel::default()
        }
    }

    pub(crate) fn is_silent(&self) -> bool {
        self.playing.is_none()
    }

    /// Queues the sound like [`AudioSink::queue`]. Missing sounds and files
    /// the target cannot read are left out, like in Electrip 1.
    pub(crate) fn queue(&mut self, sink: &mut dyn AudioSink, sound: Option<&Path>) {
        let Some(sound) = sound else {
            return;
        };
        let Some(length) = sink.length(sound).ok().filter(|l| !l.is_zero()) else {
            return;
        };
        sink.queue(self.id, sound);
        if self.playing.is_none() {
            self.playing = Some(length);
        } else {
            self.waiting = Some(length);
        }
    }

    pub(crate) fn stop(&mut self, sink: &mut dyn AudioSink) {
        sink.stop(self.id);
        self.playing = None;
        self.waiting = None;
    }

    /// Lets up to `elapsed` pass until the current sound ends and returns
    /// whether it ended; the rest of `elapsed` stays. The waiting sound
    /// then plays. Time without a sound is lost: a sound queued on a
    /// silent channel starts when the target gets it.
    pub(crate) fn advance(&mut self, elapsed: &mut Duration) -> bool {
        let Some(playing) = self.playing else {
            *elapsed = Duration::ZERO;
            return false;
        };
        if playing > *elapsed {
            self.playing = Some(playing - *elapsed);
            *elapsed = Duration::ZERO;
            return false;
        }
        *elapsed -= playing;
        self.playing = self.waiting.take();
        if self.playing.is_none() {
            *elapsed = Duration::ZERO;
        }
        true
    }
}

#[cfg(test)]
pub(crate) mod tests;
