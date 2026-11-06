use super::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

/// What an audio target got, one line per call: "<channel> <sound>",
/// "<channel> <sound> after <delay>", "<channel> stop",
/// "<channel> <sound> fade in <fade>" or "<channel> fade out <fade>".
/// Channel 0 of a loco is named by the loco, others by loco and number
/// ("1.2").
pub(crate) type Played = Arc<Mutex<Vec<String>>>;

/// An audio target that knows the length of the sounds in `lengths` and
/// logs what it gets.
#[derive(Default)]
pub(crate) struct LogSink {
    pub lengths: HashMap<String, f64>,
    pub played: Played,
}

impl LogSink {
    /// A target where each named sound lasts as long as given.
    pub(crate) fn new(lengths: &[(&str, f64)]) -> Self {
        let lengths = lengths.iter().map(|(s, l)| (s.to_string(), *l)).collect();
        LogSink {
            lengths,
            played: Played::default(),
        }
    }

    /// Returns and forgets what the target got.
    pub(crate) fn take(&self) -> Vec<String> {
        std::mem::take(&mut self.played.lock().unwrap())
    }
}

impl AudioSink for LogSink {
    fn length(&mut self, sound: &Path) -> Result<Duration, String> {
        let name = sound.to_string_lossy();
        let length = self.lengths.get(name.as_ref()).ok_or("unknown sound")?;
        Ok(Duration::from_secs_f64(*length))
    }

    fn queue(&mut self, channel: ChannelId, sound: &Path) {
        let line = format!("{} {}", name(channel), sound.display());
        self.played.lock().unwrap().push(line);
    }

    fn play(&mut self, channel: ChannelId, sound: &Path, delay: Duration) {
        let line = format!("{} {} after {delay:?}", name(channel), sound.display());
        self.played.lock().unwrap().push(line);
    }

    fn stop(&mut self, channel: ChannelId) {
        self.played
            .lock()
            .unwrap()
            .push(format!("{} stop", name(channel)));
    }

    fn fade_in(&mut self, channel: ChannelId, sound: &Path, fade: Duration) {
        let line = format!("{} {} fade in {fade:?}", name(channel), sound.display());
        self.played.lock().unwrap().push(line);
    }

    fn fade_out(&mut self, channel: ChannelId, fade: Duration) {
        let line = format!("{} fade out {fade:?}", name(channel));
        self.played.lock().unwrap().push(line);
    }
}

fn name(channel: ChannelId) -> String {
    match channel.nr {
        0 => channel.loco.to_string(),
        nr => format!("{}.{nr}", channel.loco),
    }
}

/// Channel 0 of the loco.
fn channel(loco: u32) -> Channel {
    Channel::new(ChannelId { loco, nr: 0 })
}

fn seconds(seconds: f64) -> Duration {
    Duration::from_secs_f64(seconds)
}

#[test]
fn a_silent_channel_plays_at_once_a_busy_one_after_the_sound() {
    let mut sink = LogSink::new(&[("a", 1.0), ("b", 2.0)]);
    let mut channel = channel(3);
    channel.queue(&mut sink, Some(Path::new("a")));
    channel.queue(&mut sink, Some(Path::new("b")));
    assert_eq!(sink.take(), ["3 a", "3 b"]);

    let mut elapsed = seconds(1.5);
    assert!(channel.advance(&mut elapsed));
    assert_eq!(elapsed, seconds(0.5));
    assert!(!channel.advance(&mut elapsed));
    assert_eq!(channel.playing, Some(seconds(1.5)));
}

#[test]
fn time_without_a_sound_is_lost() {
    let mut sink = LogSink::new(&[("a", 1.0)]);
    let mut channel = channel(1);
    channel.queue(&mut sink, Some(Path::new("a")));
    let mut elapsed = seconds(3.0);
    assert!(channel.advance(&mut elapsed));
    assert_eq!(elapsed, Duration::ZERO);
    assert!(channel.is_silent());
}

#[test]
fn missing_and_unknown_sounds_are_left_out() {
    let mut sink = LogSink::new(&[("empty", 0.0)]);
    let mut channel = channel(1);
    for sound in [None, Some("unknown"), Some("empty")] {
        channel.queue(&mut sink, sound.map(Path::new));
    }
    assert!(channel.is_silent());
    assert!(sink.take().is_empty());
}

#[test]
fn stop_silences_and_drops_the_waiting_sound() {
    let mut sink = LogSink::new(&[("a", 1.0)]);
    let mut channel = channel(1);
    channel.queue(&mut sink, Some(Path::new("a")));
    channel.queue(&mut sink, Some(Path::new("a")));
    channel.stop(&mut sink);
    assert!(channel.is_silent());
    assert!(!channel.advance(&mut seconds(5.0)));
    assert_eq!(sink.take(), ["1 a", "1 a", "1 stop"]);
}
