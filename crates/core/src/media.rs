//! Pictures and sounds in the library, each file named by the SHA-256 of
//! its content (ADR 0003). A file goes by its path in the library, e.g.
//! `sounds/<SHA-256>.ogg`; a loco names its sounds so, and instances
//! exchange missing files by it (N-04).

use crate::audio::{AudioSink, ChannelId};
use crate::config::Config;
use sha2::{Digest, Sha256};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::time::Duration;

/// The directory of the pictures in the library (B-05).
pub(crate) const PICTURES: &str = "media";
/// The directory of the sounds in the library.
pub const SOUNDS: &str = "sounds";

/// Saves the sound `bytes` with the extension of `source` in the library;
/// returns its path there.
pub fn add_sound(library: &Path, bytes: &[u8], source: &Path) -> io::Result<PathBuf> {
    let path = sound_path(bytes, source);
    fs::create_dir_all(library.join(SOUNDS))?;
    fs::write(library.join(&path), bytes)?;
    Ok(path.into())
}

/// The path of a sound in the library by its content, with the extension
/// of `source`.
pub(crate) fn sound_path(bytes: &[u8], source: &Path) -> String {
    let name = content_name(bytes);
    match source.extension() {
        Some(extension) => format!("{SOUNDS}/{name}.{}", extension.to_string_lossy()),
        None => format!("{SOUNDS}/{name}"),
    }
}

/// The path of the picture `name` in the library.
pub(crate) fn picture_path(name: &str) -> String {
    format!("{PICTURES}/{name}.png")
}

/// The file of a sound: one of the library there, any other as it is.
pub fn file(library: &Path, sound: &Path) -> PathBuf {
    match sound.to_str().map(hash) {
        Some(Ok(_)) => library.join(sound),
        _ => sound.into(),
    }
}

/// The content of the picture or sound at `path` in the library; other
/// paths cannot reach a file.
pub fn read(library: &Path, path: &str) -> io::Result<Vec<u8>> {
    hash(path)?;
    fs::read(library.join(path))
}

/// Saves a picture or sound of another instance at its `path` in the
/// library, if the path names the content.
pub fn write(library: &Path, path: &str, bytes: &[u8]) -> io::Result<()> {
    if hash(path)? != content_name(bytes) {
        return Err(io::Error::other(format!("the content is not {path}")));
    }
    let path = library.join(path);
    fs::create_dir_all(path.parent().unwrap_or(library))?;
    fs::write(path, bytes)
}

/// The pictures and sounds the locos of `config` use from the library and
/// it lacks.
pub fn missing(library: &Path, config: &Config) -> Vec<String> {
    let mut files = Vec::new();
    for loco in &config.locos {
        files.extend(loco.picture().map(picture_path));
        loco.clone().map_sounds(|sound| {
            files.extend(sound.to_str().map(String::from));
            None
        });
    }
    files.retain(|file| hash(file).is_ok() && !library.join(file).exists());
    files.sort();
    files.dedup();
    files
}

/// The SHA-256 the path of a picture or sound names, an error for other
/// paths.
fn hash(path: &str) -> io::Result<&str> {
    let invalid = || io::Error::other(format!("there is no picture or sound {path}"));
    let (dir, file) = path.split_once('/').ok_or_else(invalid)?;
    let (hash, extension) = file.split_once('.').unwrap_or((file, ""));
    let valid = [PICTURES, SOUNDS].contains(&dir)
        && hash.len() == 64
        && hash.bytes().all(|b| b.is_ascii_hexdigit())
        && extension.bytes().all(|b| b.is_ascii_alphanumeric());
    if valid { Ok(hash) } else { Err(invalid()) }
}

/// A file name from the content, the same for the same content.
pub(crate) fn content_name(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

/// The audio target of an instance: it plays the sounds of the library
/// from there and any other sound file as it is.
pub struct LibrarySink {
    pub sink: crate::audio::Audio,
    pub library: PathBuf,
}

impl AudioSink for LibrarySink {
    fn length(&mut self, sound: &Path) -> Result<Duration, String> {
        self.sink.length(&file(&self.library, sound))
    }

    fn queue(&mut self, channel: ChannelId, sound: &Path) {
        self.sink.queue(channel, &file(&self.library, sound));
    }

    fn play(&mut self, channel: ChannelId, sound: &Path, delay: Duration) {
        self.sink.play(channel, &file(&self.library, sound), delay);
    }

    fn stop(&mut self, channel: ChannelId) {
        self.sink.stop(channel);
    }

    fn fade_in(&mut self, channel: ChannelId, sound: &Path, fade: Duration) {
        self.sink
            .fade_in(channel, &file(&self.library, sound), fade);
    }

    fn fade_out(&mut self, channel: ChannelId, fade: Duration) {
        self.sink.fade_out(channel, fade);
    }

    fn devices(&mut self) -> Vec<String> {
        self.sink.devices()
    }

    fn route(&mut self, loco: u32, device: Option<&str>) {
        self.sink.route(loco, device);
    }
}

#[cfg(test)]
mod tests;
