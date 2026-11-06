use std::fs;
use std::iter;
use std::num::NonZero;
use std::path::{Path, PathBuf};
use std::time::Duration;

use electrip_core::audio::{AudioSink, ChannelId};
use rodio::mixer::{MixerSource, mixer};

use super::{Output, Speaker};
use crate::tests::extract;

const RATE: u32 = 8_000;
const CHANNEL: ChannelId = ChannelId { loco: 1, nr: 0 };

/// A speaker on a mono mixer at `RATE` and the output of the mixer.
fn speaker() -> (Speaker, MixerSource) {
    let (channels, rate) = (NonZero::<u16>::MIN, NonZero::new(RATE).unwrap());
    let (mixer, output) = mixer(channels, rate);
    let output_format = Output {
        mixer,
        channels,
        rate,
    };
    (Speaker::new(Some(output_format)), output)
}

/// Writes a mono 16 bit WAV file of `samples` samples, all at `level`.
fn wav(dir: &Path, name: &str, rate: u32, level: i16, samples: u32) -> PathBuf {
    let data = samples * 2;
    let mut bytes = b"RIFF".to_vec();
    bytes.extend((36 + data).to_le_bytes());
    bytes.extend(b"WAVEfmt ");
    bytes.extend(16u32.to_le_bytes());
    bytes.extend(1u16.to_le_bytes());
    bytes.extend(1u16.to_le_bytes());
    bytes.extend(rate.to_le_bytes());
    bytes.extend((rate * 2).to_le_bytes());
    bytes.extend(2u16.to_le_bytes());
    bytes.extend(16u16.to_le_bytes());
    bytes.extend(b"data");
    bytes.extend(data.to_le_bytes());
    for _ in 0..samples {
        bytes.extend(level.to_le_bytes());
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
    let file = wav(dir.path(), "a.wav", RATE / 2, 0x4000, 100);
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
    let first = wav(dir.path(), "first.wav", RATE, 0x2000, 100);
    let waiting = wav(dir.path(), "waiting.wav", RATE, 0x4000, 100);
    let last = wav(dir.path(), "last.wav", RATE, 0x6000, 100);
    let (mut speaker, mut output) = speaker();
    speaker.queue(CHANNEL, &first);
    speaker.queue(CHANNEL, &waiting);
    speaker.queue(CHANNEL, &last);
    assert_eq!(sound(&mut output, 1000), [(0.25, 100), (0.75, 100)]);
}

#[test]
fn channels_play_at_the_same_time() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, 0x2000, 100);
    let (mut speaker, mut output) = speaker();
    speaker.queue(CHANNEL, &file);
    speaker.queue(ChannelId { nr: 1, ..CHANNEL }, &file);
    assert_eq!(sound(&mut output, 1000), [(0.5, 100)]);
}

#[test]
fn stop_silences_the_channel() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, 0x2000, 1000);
    let (mut speaker, mut output) = speaker();
    speaker.queue(CHANNEL, &file);
    assert_eq!(runs(&mut output, 100), [(0.25, 100)]);
    speaker.stop(CHANNEL);
    assert_eq!(runs(&mut output, 100), [(0.0, 100)]);
}

#[test]
fn play_starts_after_the_delay_and_cuts_off_the_channel() {
    let dir = tempfile::tempdir().unwrap();
    let old = wav(dir.path(), "old.wav", RATE, 0x2000, 1000);
    let new = wav(dir.path(), "new.wav", RATE, 0x4000, 100);
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
    let file = wav(dir.path(), "a.wav", RATE, 0x4000, 200);
    let (mut speaker, mut output) = speaker();
    speaker.fade_in(CHANNEL, &file, Duration::from_millis(10));
    let runs = sound(&mut output, 1000);
    assert_eq!(runs, [(0.25, 40), (0.5, 140)]);
}

#[test]
fn fade_out_ends_in_silence() {
    let dir = tempfile::tempdir().unwrap();
    let file = wav(dir.path(), "a.wav", RATE, 0x4000, 10_000);
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
    let file = wav(dir.path(), "a.wav", RATE, 0x4000, 800);
    let mut speaker = Speaker::new(None);
    assert_eq!(speaker.length(&file).unwrap(), Duration::from_millis(100));
    speaker.queue(CHANNEL, &file);
    assert!(speaker.channels.is_empty());
    assert!(speaker.length(&dir.path().join("missing.wav")).is_err());
}
