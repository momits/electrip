use super::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

/// What an audio target got, one line per call: "<channel> <sound>" or
/// "<channel> stop".
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
    fn length(&mut self, sound: &Path) -> Result<f64, String> {
        let name = sound.to_string_lossy();
        self.lengths
            .get(name.as_ref())
            .copied()
            .ok_or("unknown sound".into())
    }

    fn queue(&mut self, channel: u32, sound: &Path) {
        let line = format!("{channel} {}", sound.display());
        self.played.lock().unwrap().push(line);
    }

    fn stop(&mut self, channel: u32) {
        self.played.lock().unwrap().push(format!("{channel} stop"));
    }
}

fn seconds(seconds: f64) -> Duration {
    Duration::from_secs_f64(seconds)
}

#[test]
fn a_silent_channel_plays_at_once_a_busy_one_after_the_sound() {
    let mut sink = LogSink::new(&[("a", 1.0), ("b", 2.0)]);
    let mut channel = Channel::new(3);
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
    let mut channel = Channel::new(1);
    channel.queue(&mut sink, Some(Path::new("a")));
    let mut elapsed = seconds(3.0);
    assert!(channel.advance(&mut elapsed));
    assert_eq!(elapsed, Duration::ZERO);
    assert!(channel.is_silent());
}

#[test]
fn missing_and_unknown_sounds_are_left_out() {
    let mut sink = LogSink::new(&[("empty", 0.0)]);
    let mut channel = Channel::new(1);
    for sound in [None, Some("unknown"), Some("empty")] {
        channel.queue(&mut sink, sound.map(Path::new));
    }
    assert!(channel.is_silent());
    assert!(sink.take().is_empty());
}

#[test]
fn stop_silences_and_drops_the_waiting_sound() {
    let mut sink = LogSink::new(&[("a", 1.0)]);
    let mut channel = Channel::new(1);
    channel.queue(&mut sink, Some(Path::new("a")));
    channel.queue(&mut sink, Some(Path::new("a")));
    channel.stop(&mut sink);
    assert!(channel.is_silent());
    assert!(!channel.advance(&mut seconds(5.0)));
    assert_eq!(sink.take(), ["1 a", "1 a", "1 stop"]);
}
