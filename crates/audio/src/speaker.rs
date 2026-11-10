//! The sound cards as the audio target of the locos (B-18, N-05). Each
//! channel is one source in the mixer of the sound card of its loco. Its
//! sounds are converted to the format of the mixer first, so the channel
//! can switch between them at any sample.

use std::collections::{HashMap, HashSet};
use std::iter;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Sender};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use std::{thread, vec};

use electrip_core::audio::{AudioSink, ChannelId};
use rodio::buffer::SamplesBuffer;
use rodio::cpal::traits::{DeviceTrait, HostTrait};
use rodio::mixer::Mixer;
use rodio::source::UniformSourceIterator;
use rodio::{
    ChannelCount, Device, DeviceSinkBuilder, MixerDeviceSink, Sample, SampleRate, Source, cpal,
};

use crate::open;

type Samples = Box<dyn Iterator<Item = Sample> + Send>;

/// The sounds decoded so far.
type Decoded = Arc<Mutex<HashMap<PathBuf, SamplesBuffer>>>;

/// A mixer and its format.
pub(crate) struct Output {
    pub(crate) mixer: Mixer,
    pub(crate) channels: ChannelCount,
    pub(crate) rate: SampleRate,
    /// The device plays the mixer as long as it lives; `None` for a mixer
    /// without one, e.g. in tests.
    pub(crate) _device: Option<MixerDeviceSink>,
    /// Whether the output no longer plays where it should, so it has to be
    /// opened again.
    pub(crate) gone: Box<dyn FnMut() -> bool + Send>,
}

/// Opens the output on the named device, `None` on the default one.
pub(crate) type Open = Box<dyn FnMut(Option<&str>) -> Result<Output, String> + Send>;

/// Plays the sounds of each loco into the output of its device (N-05).
/// Without an output it only knows the lengths of the sounds, so the sound
/// models still run.
pub struct Speaker {
    outputs: Outputs,
    /// The sounds of each channel and the number of the output they play on.
    channels: HashMap<ChannelId, (u64, Arc<Mutex<Sounds>>)>,
    decoded: Decoded,
    /// The sounds sent to the thread that decodes them ahead.
    prepared: HashSet<PathBuf>,
    prepare: Sender<PathBuf>,
}

/// The outputs of the locos, each opened when a loco first plays on it.
struct Outputs {
    open: Open,
    /// By device with the number of their opening, or when the device last
    /// failed to open.
    opened: HashMap<Option<String>, Result<(u64, Output), Instant>>,
    openings: u64,
    /// The devices of the locos that do not play on the default one.
    routes: HashMap<u32, String>,
}

/// The sounds of a channel.
#[derive(Default)]
struct Sounds {
    playing: Option<Samples>,
    waiting: Option<Samples>,
    stopped: bool,
}

/// The speaker on the sound cards of the computer.
pub fn sound_card() -> Speaker {
    Speaker::new(Box::new(open_device))
}

/// Opens the named output device, `None` the default one. The output is
/// gone when its stream fails or, for the default one, when the computer
/// has another default device; that is checked at most once a second.
fn open_device(name: Option<&str>) -> Result<Output, String> {
    let device = match name {
        None => default_device().ok_or("there is no default output device")?,
        Some(name) => find_device(name)?,
    };
    let opened_on = device_name(&device);
    let failed = Arc::new(AtomicBool::new(false));
    let fail = Arc::clone(&failed);
    let device = DeviceSinkBuilder::from_device(device)
        .map(|builder| {
            builder.with_error_callback(move |e| {
                eprintln!("ERROR the output device failed: {e}");
                fail.store(true, Ordering::Relaxed);
            })
        })
        .and_then(|builder| builder.open_sink_or_fallback())
        .map_err(|e| e.to_string())?;
    let follows_default = name.is_none();
    let mut checked = Instant::now();
    let gone = move || {
        if failed.load(Ordering::Relaxed) {
            return true;
        }
        if !follows_default || checked.elapsed() < Duration::from_secs(1) {
            return false;
        }
        checked = Instant::now();
        default_device().and_then(|d| device_name(&d)) != opened_on
    };
    Ok(Output {
        mixer: device.mixer().clone(),
        channels: device.config().channel_count(),
        rate: device.config().sample_rate(),
        _device: Some(device),
        gone: Box::new(gone),
    })
}

fn default_device() -> Option<Device> {
    cpal::default_host().default_output_device()
}

fn device_name(device: &Device) -> Option<String> {
    Some(device.description().ok()?.name().to_string())
}

fn find_device(name: &str) -> Result<Device, String> {
    output_devices()
        .into_iter()
        .find(|(n, _)| n == name)
        .map(|(_, device)| device)
        .ok_or_else(|| format!("there is no output device {name:?}"))
}

/// The output devices of the computer by name.
fn output_devices() -> Vec<(String, Device)> {
    let Ok(devices) = cpal::default_host().output_devices() else {
        return Vec::new();
    };
    devices
        .filter_map(|d| Some((device_name(&d)?, d)))
        .collect()
}

impl Speaker {
    pub(crate) fn new(open: Open) -> Self {
        let decoded = Decoded::default();
        let (prepare, sounds) = mpsc::channel::<PathBuf>();
        let ahead = Arc::clone(&decoded);
        let spawned = thread::Builder::new().spawn(move || {
            for sound in sounds {
                let _ = decode(&ahead, &sound);
            }
        });
        if let Err(e) = spawned {
            eprintln!("ERROR cannot decode the sounds ahead: {e}");
        }
        Speaker {
            outputs: Outputs {
                open,
                opened: HashMap::new(),
                openings: 0,
                routes: HashMap::new(),
            },
            channels: HashMap::new(),
            decoded,
            prepared: HashSet::new(),
            prepare,
        }
    }

    /// Changes the sounds of the channel, if its loco has an output; a new
    /// channel, or one whose output was opened again, joins the mixer of the
    /// output.
    fn change(&mut self, id: ChannelId, change: impl FnOnce(&mut Sounds, &Output)) {
        let Some((opening, output)) = self.outputs.of(id.loco) else {
            return;
        };
        let (_, sounds) = self
            .channels
            .entry(id)
            .and_modify(|channel| {
                if channel.0 != opening {
                    *channel = (opening, output.join());
                }
            })
            .or_insert_with(|| (opening, output.join()));
        if let Ok(mut sounds) = sounds.lock() {
            change(&mut sounds, output);
        }
    }
}

impl Outputs {
    /// The output of the loco and the number of its opening. A device that
    /// cannot be opened is reported once and tried again each second; its
    /// locos play on the default device meanwhile.
    fn of(&mut self, loco: u32) -> Option<(u64, &Output)> {
        let mut device = self.routes.get(&loco).cloned();
        if !self.try_open(&device) {
            device = None;
            self.try_open(&device);
        }
        let (opening, output) = self.opened.get(&device)?.as_ref().ok()?;
        Some((*opening, output))
    }

    /// Opens the device if it is not open, unless it failed less than a
    /// second ago; returns whether it is open.
    fn try_open(&mut self, device: &Option<String>) -> bool {
        let (failed_before, open) = match self.opened.get_mut(device) {
            Some(Ok((_, output))) => (false, (output.gone)()),
            Some(Err(failed)) => (true, failed.elapsed() >= Duration::from_secs(1)),
            None => (false, true),
        };
        if open {
            self.openings += 1;
            let output = (self.open)(device.as_deref())
                .map(|output| (self.openings, output))
                .map_err(|e| {
                    if !failed_before {
                        let name = device.as_deref().unwrap_or("default");
                        eprintln!("ERROR cannot open the output device {name}: {e}");
                    }
                    Instant::now()
                });
            self.opened.insert(device.clone(), output);
        }
        matches!(self.opened.get(device), Some(Ok(_)))
    }
}

impl Output {
    /// The samples of the sound in the format of the output.
    fn convert(&self, sound: SamplesBuffer) -> Samples {
        Box::new(UniformSourceIterator::new(sound, self.channels, self.rate))
    }

    /// A new channel in the mixer.
    fn join(&self) -> Arc<Mutex<Sounds>> {
        let sounds = Arc::default();
        self.mixer.add(ChannelSource {
            sounds: Arc::clone(&sounds),
            frame: Vec::new().into_iter(),
            channels: self.channels,
            rate: self.rate,
        });
        sounds
    }

    /// The number of samples the output plays in `duration`.
    fn samples_in(&self, duration: Duration) -> usize {
        let frames = duration.as_secs_f64() * f64::from(self.rate.get());
        frames as usize * usize::from(self.channels.get())
    }
}

impl AudioSink for Speaker {
    fn length(&mut self, sound: &Path) -> Result<Duration, String> {
        Ok(decode(&self.decoded, sound)?
            .total_duration()
            .unwrap_or_default())
    }

    /// Decodes the sound in another thread, once.
    fn prepare(&mut self, sound: &Path) {
        if !self.prepared.contains(sound) {
            self.prepared.insert(sound.into());
            let _ = self.prepare.send(sound.into());
        }
    }

    fn queue(&mut self, id: ChannelId, sound: &Path) {
        let Ok(decoded) = decode(&self.decoded, sound) else {
            return;
        };
        self.change(id, |sounds, output| {
            let samples = output.convert(decoded);
            match sounds.playing {
                Some(_) => sounds.waiting = Some(samples),
                None => sounds.playing = Some(samples),
            }
        });
    }

    fn play(&mut self, id: ChannelId, sound: &Path, delay: Duration) {
        let Ok(decoded) = decode(&self.decoded, sound) else {
            return;
        };
        self.change(id, |sounds, output| {
            let before = sounds.playing.take().into_iter().flatten();
            let before = before
                .chain(iter::repeat(0.0))
                .take(output.samples_in(delay));
            sounds.playing = Some(Box::new(before.chain(output.convert(decoded))));
            sounds.waiting = None;
        });
    }

    fn stop(&mut self, id: ChannelId) {
        if let Some((_, sounds)) = self.channels.remove(&id)
            && let Ok(mut sounds) = sounds.lock()
        {
            sounds.stopped = true;
        }
    }

    fn fade_in(&mut self, id: ChannelId, sound: &Path, fade: Duration) {
        let Ok(decoded) = decode(&self.decoded, sound) else {
            return;
        };
        self.change(id, |sounds, output| {
            let fade = output.samples_in(fade);
            let samples = output.convert(decoded);
            let rising = samples.enumerate().map(move |(i, s)| s * gain(i, fade));
            sounds.playing = Some(Box::new(rising));
            sounds.waiting = None;
        });
    }

    fn fade_out(&mut self, id: ChannelId, fade: Duration) {
        self.change(id, |sounds, output| {
            let fade = output.samples_in(fade);
            let playing = sounds.playing.take().into_iter().flatten().take(fade);
            let falling = playing
                .enumerate()
                .map(move |(i, s)| s * (1.0 - gain(i, fade)));
            sounds.playing = Some(Box::new(falling));
            sounds.waiting = None;
        });
    }

    fn devices(&mut self) -> Vec<String> {
        output_devices().into_iter().map(|(name, _)| name).collect()
    }

    /// The sounds of the loco stop when it changes the device; the next
    /// ones play on the new device.
    fn route(&mut self, loco: u32, device: Option<&str>) {
        let routes = &mut self.outputs.routes;
        if routes.get(&loco).map(String::as_str) == device {
            return;
        }
        match device {
            Some(device) => routes.insert(loco, device.to_string()),
            None => routes.remove(&loco),
        };
        let moved: Vec<_> = self
            .channels
            .keys()
            .filter(|c| c.loco == loco)
            .copied()
            .collect();
        for id in moved {
            self.stop(id);
        }
    }
}

/// The sound, decoded once. Decoding it whole also avoids a bug in rodio:
/// the first span of an OGG file has no samples, and a conversion of the
/// decoder ends there.
fn decode(decoded: &Decoded, sound: &Path) -> Result<SamplesBuffer, String> {
    if let Some(samples) = decoded.lock().ok().and_then(|d| d.get(sound).cloned()) {
        return Ok(samples);
    }
    let decoder = open(sound)?;
    let (channels, rate) = (decoder.channels(), decoder.sample_rate());
    let samples = SamplesBuffer::new(channels, rate, decoder.collect::<Vec<_>>());
    if let Ok(mut decoded) = decoded.lock() {
        decoded.insert(sound.into(), samples.clone());
    }
    Ok(samples)
}

/// The share of a fade over `n` samples reached at sample `i`.
fn gain(i: usize, n: usize) -> f32 {
    if i >= n { 1.0 } else { i as f32 / n as f32 }
}

impl Sounds {
    /// The next sample of the playing sound, then of the waiting one, then
    /// silence.
    fn next_sample(&mut self) -> Sample {
        loop {
            if let Some(sample) = self.playing.as_mut().and_then(Iterator::next) {
                return sample;
            }
            self.playing = self.waiting.take();
            if self.playing.is_none() {
                return 0.0;
            }
        }
    }
}

/// A channel in the mixer. It takes whole frames from its sounds, so a
/// change of the sounds keeps left and right in place.
struct ChannelSource {
    sounds: Arc<Mutex<Sounds>>,
    frame: vec::IntoIter<Sample>,
    channels: ChannelCount,
    rate: SampleRate,
}

impl Iterator for ChannelSource {
    type Item = Sample;

    fn next(&mut self) -> Option<Sample> {
        if let Some(sample) = self.frame.next() {
            return Some(sample);
        }
        let mut sounds = self.sounds.lock().ok()?;
        if sounds.stopped {
            return None;
        }
        let frame: Vec<_> = (0..self.channels.get())
            .map(|_| sounds.next_sample())
            .collect();
        self.frame = frame.into_iter();
        self.frame.next()
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
