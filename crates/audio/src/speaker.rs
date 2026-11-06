//! The sound card as the audio target of the locos (B-18). Each channel is
//! one source in the mixer of the sound card. Its sounds are converted to
//! the format of the mixer first, so the channel can switch between them at
//! any sample.

use std::collections::HashMap;
use std::iter;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use electrip_core::audio::{AudioSink, ChannelId};
use rodio::buffer::SamplesBuffer;
use rodio::mixer::Mixer;
use rodio::source::UniformSourceIterator;
use rodio::{ChannelCount, DeviceSinkBuilder, MixerDeviceSink, Sample, SampleRate, Source};

use crate::open;

type Samples = Box<dyn Iterator<Item = Sample> + Send>;

/// The mixer and its format.
pub struct Output {
    pub mixer: Mixer,
    pub channels: ChannelCount,
    pub rate: SampleRate,
}

/// Plays the sounds into the output. Without one it only knows the lengths
/// of the sounds, so the sound models still run.
pub struct Speaker {
    output: Option<Output>,
    channels: HashMap<ChannelId, Arc<Mutex<Sounds>>>,
    decoded: HashMap<PathBuf, SamplesBuffer>,
}

/// The sounds of a channel.
#[derive(Default)]
struct Sounds {
    playing: Option<Samples>,
    waiting: Option<Samples>,
    stopped: bool,
}

/// The speaker on the default sound card and the device, which plays as
/// long as it lives.
pub fn sound_card() -> Result<(Speaker, MixerDeviceSink), String> {
    let device = DeviceSinkBuilder::open_default_sink().map_err(|e| e.to_string())?;
    let output = Output {
        mixer: device.mixer().clone(),
        channels: device.config().channel_count(),
        rate: device.config().sample_rate(),
    };
    Ok((Speaker::new(Some(output)), device))
}

impl Speaker {
    pub fn new(output: Option<Output>) -> Self {
        Speaker {
            output,
            channels: HashMap::new(),
            decoded: HashMap::new(),
        }
    }

    /// The sound, decoded once. Decoding it whole also avoids a bug in
    /// rodio: the first span of an OGG file has no samples, and a
    /// conversion of the decoder ends there.
    fn decode(&mut self, sound: &Path) -> Result<SamplesBuffer, String> {
        if let Some(decoded) = self.decoded.get(sound) {
            return Ok(decoded.clone());
        }
        let decoder = open(sound)?;
        let (channels, rate) = (decoder.channels(), decoder.sample_rate());
        let decoded = SamplesBuffer::new(channels, rate, decoder.collect::<Vec<_>>());
        self.decoded.insert(sound.into(), decoded.clone());
        Ok(decoded)
    }

    /// The samples of the sound in the format of the output, if there is
    /// an output and the sound can be read.
    fn samples(&mut self, sound: &Path) -> Option<Samples> {
        let decoded = self.decode(sound).ok()?;
        let output = self.output.as_ref()?;
        let samples = UniformSourceIterator::new(decoded, output.channels, output.rate);
        Some(Box::new(samples))
    }

    /// The number of samples the output plays in `duration`.
    fn samples_in(&self, duration: Duration) -> usize {
        self.output.as_ref().map_or(0, |o| {
            let frames = duration.as_secs_f64() * f64::from(o.rate.get());
            frames as usize * usize::from(o.channels.get())
        })
    }

    /// Changes the sounds of the channel; a new channel joins the mixer.
    fn change(&mut self, id: ChannelId, change: impl FnOnce(&mut Sounds)) {
        let Some(output) = &self.output else {
            return;
        };
        let sounds = self.channels.entry(id).or_insert_with(|| {
            let sounds = Arc::default();
            output.mixer.add(ChannelSource {
                sounds: Arc::clone(&sounds),
                channels: output.channels,
                rate: output.rate,
            });
            sounds
        });
        if let Ok(mut sounds) = sounds.lock() {
            change(&mut sounds);
        }
    }
}

impl AudioSink for Speaker {
    fn length(&mut self, sound: &Path) -> Result<Duration, String> {
        Ok(self.decode(sound)?.total_duration().unwrap_or_default())
    }

    fn queue(&mut self, id: ChannelId, sound: &Path) {
        if let Some(samples) = self.samples(sound) {
            self.change(id, |sounds| match sounds.playing {
                Some(_) => sounds.waiting = Some(samples),
                None => sounds.playing = Some(samples),
            });
        }
    }

    fn play(&mut self, id: ChannelId, sound: &Path, delay: Duration) {
        let Some(samples) = self.samples(sound) else {
            return;
        };
        let delay = self.samples_in(delay);
        self.change(id, |sounds| {
            let before = sounds.playing.take().into_iter().flatten();
            let before = before.chain(iter::repeat(0.0)).take(delay);
            sounds.playing = Some(Box::new(before.chain(samples)));
            sounds.waiting = None;
        });
    }

    fn stop(&mut self, id: ChannelId) {
        if let Some(Ok(mut sounds)) = self.channels.remove(&id).as_ref().map(|s| s.lock()) {
            sounds.stopped = true;
        }
    }

    fn fade_in(&mut self, id: ChannelId, sound: &Path, fade: Duration) {
        let fade = self.samples_in(fade);
        if let Some(samples) = self.samples(sound) {
            let rising = samples.enumerate().map(move |(i, s)| s * gain(i, fade));
            self.change(id, |sounds| {
                sounds.playing = Some(Box::new(rising));
                sounds.waiting = None;
            });
        }
    }

    fn fade_out(&mut self, id: ChannelId, fade: Duration) {
        let fade = self.samples_in(fade);
        self.change(id, |sounds| {
            let playing = sounds.playing.take().into_iter().flatten().take(fade);
            let falling = playing
                .enumerate()
                .map(move |(i, s)| s * (1.0 - gain(i, fade)));
            sounds.playing = Some(Box::new(falling));
            sounds.waiting = None;
        });
    }
}

/// The share of a fade over `n` samples reached at sample `i`.
fn gain(i: usize, n: usize) -> f32 {
    (i as f32 / n as f32).min(1.0)
}

/// A channel in the mixer: its playing sound, then the waiting one, then
/// silence until it stops.
struct ChannelSource {
    sounds: Arc<Mutex<Sounds>>,
    channels: ChannelCount,
    rate: SampleRate,
}

impl Iterator for ChannelSource {
    type Item = Sample;

    fn next(&mut self) -> Option<Sample> {
        let mut sounds = self.sounds.lock().ok()?;
        if sounds.stopped {
            return None;
        }
        loop {
            if let Some(sample) = sounds.playing.as_mut().and_then(Iterator::next) {
                return Some(sample);
            }
            sounds.playing = sounds.waiting.take();
            if sounds.playing.is_none() {
                return Some(0.0);
            }
        }
    }
}

impl Source for ChannelSource {
    fn current_span_len(&self) -> Option<usize> {
        None
    }

    fn channels(&self) -> ChannelCount {
        self.channels
    }

    fn sample_rate(&self) -> SampleRate {
        self.rate
    }

    fn total_duration(&self) -> Option<Duration> {
        None
    }
}

#[cfg(test)]
mod tests;
