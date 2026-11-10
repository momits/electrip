//! The audio target of the locos (ADR 0004). The session host runs the sound
//! models and sends their sounds to the target; it reckons with the length
//! of the files, not with the playback (B-13).

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::time::Duration;

pub use targets::Remote;
pub(crate) use targets::Targets;

pub type Audio = Box<dyn AudioSink + Send>;

/// A channel of the audio target: the loco and its `nr`-th channel. The
/// driving sound plays on channel 0, a steam engine also on the following;
/// sound functions play above them.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
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

    /// Plays the sound on the silent channel at once, rising from silence
    /// to full volume over `fade` (B-17).
    fn fade_in(&mut self, channel: ChannelId, sound: &Path, fade: Duration);

    /// Lowers the channel to silence over `fade`, then silences it like
    /// [`AudioSink::stop`] (B-17).
    fn fade_out(&mut self, channel: ChannelId, fade: Duration);

    /// Reads the sound ahead, so it plays without delay later. A target
    /// that reads the sounds only when they play ignores it.
    fn prepare(&mut self, _sound: &Path) {}

    /// The names of the output devices (N-05).
    fn devices(&mut self) -> Vec<String> {
        Vec::new()
    }

    /// Plays the channels of the loco on the output device, `None` on the
    /// default one (N-05). A target with one output ignores it.
    fn route(&mut self, _loco: u32, _device: Option<&str>) {}
}

/// A call of an audio target, as the host sends it to another instance
/// (N-05).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "snake_case")]
pub enum AudioEvent {
    Queue {
        channel: ChannelId,
        sound: PathBuf,
    },
    Play {
        channel: ChannelId,
        sound: PathBuf,
        delay: Duration,
    },
    Stop {
        channel: ChannelId,
    },
    FadeIn {
        channel: ChannelId,
        sound: PathBuf,
        fade: Duration,
    },
    FadeOut {
        channel: ChannelId,
        fade: Duration,
    },
    Route {
        loco: u32,
        device: Option<String>,
    },
}

impl AudioEvent {
    /// Makes the call on `sink`.
    pub fn apply(&self, sink: &mut dyn AudioSink) {
        match self {
            AudioEvent::Queue { channel, sound } => sink.queue(*channel, sound),
            AudioEvent::Play {
                channel,
                sound,
                delay,
            } => sink.play(*channel, sound, *delay),
            AudioEvent::Stop { channel } => sink.stop(*channel),
            AudioEvent::FadeIn {
                channel,
                sound,
                fade,
            } => sink.fade_in(*channel, sound, *fade),
            AudioEvent::FadeOut { channel, fade } => sink.fade_out(*channel, *fade),
            AudioEvent::Route { loco, device } => sink.route(*loco, device.as_deref()),
        }
    }
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

    pub(crate) fn id(&self) -> ChannelId {
        self.id
    }

    pub(crate) fn is_silent(&self) -> bool {
        self.playing.is_none()
    }

    /// Queues the sound like [`AudioSink::queue`]. Missing sounds and files
    /// the target cannot read are left out, like in Electrip 1.
    pub(crate) fn queue(&mut self, sink: &mut dyn AudioSink, sound: Option<&Path>) {
        let Some((sound, length)) = playable(sink, sound) else {
            return;
        };
        sink.queue(self.id, sound);
        if self.playing.is_none() {
            self.playing = Some(length);
        } else {
            self.waiting = Some(length);
        }
    }

    /// Plays the sound like [`AudioSink::fade_in`]; missing sounds and
    /// files the target cannot read are left out.
    pub(crate) fn fade_in(
        &mut self,
        sink: &mut dyn AudioSink,
        sound: Option<&Path>,
        fade: Duration,
    ) {
        let Some((sound, length)) = playable(sink, sound) else {
            return;
        };
        sink.fade_in(self.id, sound, fade);
        self.playing = Some(length);
        self.waiting = None;
    }

    /// Fades out like [`AudioSink::fade_out`]; the sound ends with the fade
    /// at the latest.
    pub(crate) fn fade_out(&mut self, sink: &mut dyn AudioSink, fade: Duration) {
        sink.fade_out(self.id, fade);
        self.playing = self.playing.map(|p| p.min(fade)).filter(|p| !p.is_zero());
        self.waiting = None;
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

/// The sound and its length, unless it is missing or the target cannot
/// read it.
fn playable<'a>(sink: &mut dyn AudioSink, sound: Option<&'a Path>) -> Option<(&'a Path, Duration)> {
    let sound = sound?;
    let length = sink.length(sound).ok().filter(|l| !l.is_zero())?;
    Some((sound, length))
}

mod targets;
#[cfg(test)]
pub(crate) mod tests;
