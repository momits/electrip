use std::collections::HashMap;
use std::fs;
use std::iter;
use std::num::NonZero;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use electrip_core::audio::{AudioSink, ChannelId};
use rodio::mixer::{MixerSource, mixer};

use super::{Output, Speaker};
use crate::tests::extract;

const RATE: u32 = 8_000;
const CHANNEL: ChannelId = ChannelId { loco: 1, nr: 0 };

/// A speaker on a mono mixer at `RATE` and the output of the mixer.
fn speaker() -> (Speaker, MixerSource) {
    speaker_with(NonZero::<u16>::MIN)
}

fn speaker_with(channels: NonZero<u16>) -> (Speaker, MixerSource) {
    let rate = NonZero::new(RATE).unwrap();
    let (mixer, output) = mixer(channels, rate);
    let mut mixer = Some(mixer);
    let open = move |_: Option<&str>| {
        let mixer = mixer.take().ok_or("opened twice")?;
        Ok(Output {
            mixer,
            channels,
            rate,
            _device: None,
            gone: Box::new(|| false),
        })
    };
    (Speaker::new(Box::new(open)), output)
}

/// A speaker with a mono mixer for each of the devices, `None` the default
/// one, and the outputs of the mixers; other devices cannot be opened.
fn speaker_on(devices: &[Option<&str>]) -> (Speaker, Vec<MixerSource>) {
    let rate = NonZero::new(RATE).unwrap();
    let (mixers, outputs): (HashMap<_, _>, Vec<_>) = devices
        .iter()
        .map(|d| {
            let (mixer, output) = mixer(NonZero::<u16>::MIN, rate);
            ((d.map(str::to_string), mixer), output)
        })
        .unzip();
    let open = move |device: Option<&str>| {
        let mixer = mixers
            .get(&device.map(str::to_string))
            .ok_or("no such device")?;
        Ok(Output {
            mixer: mixer.clone(),
            channels: NonZero::<u16>::MIN,
            rate,
            _device: None,
            gone: Box::new(|| false),
        })
    };
    (Speaker::new(Box::new(open)), outputs)
}

/// Writes a 16 bit WAV file of `frames` frames, all equal to `frame`.
fn wav(dir: &Path, name: &str, rate: u32, frame: &[i16], frames: u32) -> PathBuf {
    let channels = frame.len() as u16;
    let data = frames * u32::from(channels) * 2;
    let mut bytes = b"RIFF".to_vec();
    bytes.extend((36 + data).to_le_bytes());
    bytes.extend(b"WAVEfmt ");
    bytes.extend(16u32.to_le_bytes());
    bytes.extend(1u16.to_le_bytes());
    bytes.extend(channels.to_le_bytes());
    bytes.extend(rate.to_le_bytes());
    bytes.extend((rate * u32::from(channels) * 2).to_le_bytes());
    bytes.extend((channels * 2).to_le_bytes());
    bytes.extend(16u16.to_le_bytes());
    bytes.extend(b"data");
    bytes.extend(data.to_le_bytes());
    for _ in 0..frames {
        bytes.extend(frame.iter().flat_map(|s| s.to_le_bytes()));
    }
    let path = dir.join(name);
    fs::write(&path, bytes).unwrap();
    path
}

/// The next `n` samples of the mixer as runs of the same level, each
/// level rounded to quarters. The player starts with a bit of silence.
fn runs(output: &mut MixerSource, n: usize) -> Vec<(f32, usize)> {
    let mut runs: Vec<(f32, usize)> = Vec::new();
    for sample in output.by_ref().chain(iter::repeat(0.0)).take(n) {
        let level = (sample * 4.0).round() / 4.0;
        match runs.last_mut() {
            Some((last, count)) if *last == level => *count += 1,
            _ => runs.push((level, 1)),
        }
    }
    runs
}

/// The runs without the silence at the start and at the end.
fn sound(output: &mut MixerSource, n: usize) -> Vec<(f32, usize)> {
    let mut runs = runs(output, n);
    if runs.first().is_some_and(|(level, _)| *level == 0.0) {
        runs.remove(0);
    }
    if runs.last().is_some_and(|(level, _)| *level == 0.0) {
        runs.pop();
    }
    runs
}

#[test]
fn wav_plays_at_the_sample_rate_of_the_file() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE / 2, &[0x4000], 100);
    let (mut speaker, mut output) = speaker();
    assert_eq!(speaker.length(&file).unwrap(), Duration::from_millis(25));
    speaker.queue(CHANNEL, &file);
    let runs = sound(&mut output, 1000);
    let loud: usize = runs.iter().filter(|r| r.0 == 0.5).map(|r| r.1).sum();
    assert!((195..=200).contains(&loud), "{runs:?}");
}

#[test]
fn ogg_plays() {
    let dir = tempfile::tempdir().unwrap();
    let file = extract(dir.path(), "V 60.zip", "horn.ogg");
    let (mut speaker, output) = speaker();
    let length = speaker.length(&file).unwrap();
    assert!(length > Duration::from_millis(100), "{length:?}");
    speaker.queue(CHANNEL, &file);
    assert!(output.take(8_000).any(|s| s.abs() > 0.1));
}

#[test]
fn queue_follows_without_a_gap_and_replaces_the_waiting_sound() {
    let dir = tempfile::tempdir().unwrap();
    let first = wav(dir.path(), "first.wav", RATE, &[0x2000], 100);
    let waiting = wav(dir.path(), "waiting.wav", RATE, &[0x4000], 100);
    let last = wav(dir.path(), "last.wav", RATE, &[0x6000], 100);
    let (mut speaker, mut output) = speaker();
    speaker.queue(CHANNEL, &first);
    speaker.queue(CHANNEL, &waiting);
    speaker.queue(CHANNEL, &last);
    assert_eq!(sound(&mut output, 1000), [(0.25, 100), (0.75, 100)]);
}

#[test]
fn channels_play_at_the_same_time() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x2000], 100);
    let (mut speaker, mut output) = speaker();
    speaker.queue(CHANNEL, &file);
    speaker.queue(ChannelId { nr: 1, ..CHANNEL }, &file);
    assert_eq!(sound(&mut output, 1000), [(0.5, 100)]);
}

#[test]
fn stop_silences_the_channel() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x2000], 1000);
    let (mut speaker, mut output) = speaker();
    speaker.queue(CHANNEL, &file);
    assert_eq!(runs(&mut output, 100), [(0.25, 100)]);
    speaker.stop(CHANNEL);
    assert_eq!(runs(&mut output, 100), [(0.0, 100)]);
}

#[test]
fn play_starts_after_the_delay_and_cuts_off_the_channel() {
    let dir = tempfile::tempdir().unwrap();
    let old = wav(dir.path(), "old.wav", RATE, &[0x2000], 1000);
    let new = wav(dir.path(), "new.wav", RATE, &[0x4000], 100);
    let (mut speaker, mut output) = speaker();
    speaker.play(CHANNEL, &old, Duration::ZERO);
    assert_eq!(runs(&mut output, 100), [(0.25, 100)]);
    speaker.play(CHANNEL, &new, Duration::from_millis(50));
    assert_eq!(
        runs(&mut output, 1000),
        [(0.25, 400), (0.5, 100), (0.0, 500)]
    );
}

#[test]
fn fade_in_rises_to_full_volume() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x4000], 200);
    let (mut speaker, mut output) = speaker();
    speaker.fade_in(CHANNEL, &file, Duration::from_millis(10));
    let runs = sound(&mut output, 1000);
    assert_eq!(runs, [(0.25, 40), (0.5, 140)]);
}

#[test]
fn fade_out_ends_in_silence() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x4000], 10_000);
    let (mut speaker, mut output) = speaker();
    speaker.queue(CHANNEL, &file);
    speaker.fade_out(CHANNEL, Duration::from_millis(20));
    let runs = runs(&mut output, 1000);
    assert_eq!(runs.first().map(|r| r.0), Some(0.5));
    let fading: usize = runs.iter().filter(|r| r.0 != 0.0).map(|r| r.1).sum();
    assert_eq!(runs.last(), Some(&(0.0, 1000 - fading)), "{runs:?}");
    assert!(fading < 160, "{runs:?}");
}

#[test]
fn without_a_mixer_only_lengths_are_known() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x4000], 800);
    let mut speaker = Speaker::new(Box::new(|_| Err("no sound card".into())));
    assert_eq!(speaker.length(&file).unwrap(), Duration::from_millis(100));
    speaker.queue(CHANNEL, &file);
    assert!(speaker.channels.is_empty());
    assert!(speaker.length(&dir.path().join("missing.wav")).is_err());
}

#[test]
fn a_sound_starts_with_a_whole_frame() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "stereo.wav", RATE, &[0x2000, 0x6000], 2);
    let (mut speaker, mut output) = speaker_with(NonZero::new(2).unwrap());
    speaker.play(CHANNEL, &file, Duration::ZERO);
    assert_eq!(output.next(), Some(0.25));
    speaker.play(CHANNEL, &file, Duration::ZERO);
    let samples: Vec<f32> = output.take(5).collect();
    assert_eq!(samples, [0.75, 0.25, 0.75, 0.25, 0.75]);
}

#[test]
fn each_loco_plays_on_its_device() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x2000], 100);
    let (mut speaker, mut outputs) = speaker_on(&[None, Some("USB")]);
    let other = ChannelId { loco: 2, nr: 0 };
    speaker.route(other.loco, Some("USB"));
    speaker.queue(CHANNEL, &file);
    speaker.queue(other, &file);
    speaker.queue(ChannelId { nr: 1, ..other }, &file);
    assert_eq!(sound(&mut outputs[0], 1000), [(0.25, 100)]);
    assert_eq!(sound(&mut outputs[1], 1000), [(0.5, 100)]);
}

#[test]
fn a_loco_that_changes_the_device_plays_its_next_sound_there() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x2000], 1000);
    let (mut speaker, mut outputs) = speaker_on(&[None, Some("USB")]);
    speaker.queue(CHANNEL, &file);
    assert_eq!(runs(&mut outputs[0], 100), [(0.25, 100)]);
    speaker.route(CHANNEL.loco, Some("USB"));
    assert_eq!(runs(&mut outputs[0], 100), [(0.0, 100)]);
    speaker.queue(CHANNEL, &file);
    assert_eq!(runs(&mut outputs[1], 100), [(0.25, 100)]);
}

#[test]
fn a_loco_on_a_missing_device_plays_on_the_default_one() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x2000], 100);
    let (mut speaker, mut outputs) = speaker_on(&[None]);
    speaker.route(CHANNEL.loco, Some("gone"));
    speaker.queue(CHANNEL, &file);
    assert_eq!(sound(&mut outputs[0], 1000), [(0.25, 100)]);
}

#[test]
fn a_gone_output_is_opened_again() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, &[0x2000], 1000);
    let rate = NonZero::new(RATE).unwrap();
    let gone = Arc::new(AtomicBool::new(false));
    let (old, mut old_output) = mixer(NonZero::<u16>::MIN, rate);
    let (new, mut new_output) = mixer(NonZero::<u16>::MIN, rate);
    let mut mixers = vec![new, old];
    let is_gone = Arc::clone(&gone);
    let open = move |_: Option<&str>| {
        let is_gone = Arc::clone(&is_gone);
        Ok(Output {
            mixer: mixers.pop().ok_or("no device")?,
            channels: NonZero::<u16>::MIN,
            rate,
            _device: None,
            gone: Box::new(move || is_gone.swap(false, Ordering::Relaxed)),
        })
    };
    let mut speaker = Speaker::new(Box::new(open));
    speaker.queue(CHANNEL, &file);
    assert_eq!(runs(&mut old_output, 100), [(0.25, 100)]);
    gone.store(true, Ordering::Relaxed);
    speaker.queue(CHANNEL, &file);
    assert_eq!(runs(&mut new_output, 100), [(0.25, 100)]);
}
