//! Loco packages (B-20): a loco with its picture as a ZIP archive. Electrip 2
//! writes `loco.json` with the loco and the actions its functions and sound
//! functions use, and the picture as `media/<name>.png`. A package of
//! Electrip 1 holds `<name>.loco` and the files it names.

use crate::electrip1::{self, ImportError};
use crate::function::Action;
use crate::loco::Loco;
use crate::picture;
use serde::{Deserialize, Serialize};
use std::fs::{self, File};
use std::io::{self, Read, Write};
use std::path::Path;
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

const CONTENT: &str = "loco.json";

#[derive(Debug, Clone, PartialEq)]
pub struct Package {
    /// Its picture is already in the media directory.
    pub loco: Loco,
    /// The actions the functions of the loco use, with the ids of the
    /// exporting configuration.
    pub actions: Vec<Action>,
    /// Changes made to fit the package to Electrip 2, one line each.
    pub report: Vec<String>,
}

#[derive(Serialize, Deserialize)]
struct Content {
    loco: Loco,
    actions: Vec<Action>,
}

/// Writes the loco, the `actions` its functions, sound functions and event
/// sounds use and its picture from the media directory `media` to a package
/// at `path`.
pub fn write(path: &Path, loco: &Loco, actions: &[Action], media: &Path) -> io::Result<()> {
    let used = |a: &&Action| {
        let sounds = loco.sound_functions().iter().map(|f| f.action);
        let events = loco.event_sounds().iter().map(|s| s.action);
        let functions = loco.functions().iter().map(|f| f.action);
        let mut ids = functions.chain(sounds).chain(events);
        ids.any(|id| id == a.id)
    };
    let content = Content {
        loco: loco.clone(),
        actions: actions.iter().filter(used).cloned().collect(),
    };
    let mut zip = ZipWriter::new(File::create(path)?);
    zip.start_file(CONTENT, SimpleFileOptions::default())?;
    serde_json::to_writer_pretty(&mut zip, &content)?;
    if let Some(name) = loco.picture() {
        zip.start_file(media_entry(name), SimpleFileOptions::default())?;
        zip.write_all(&fs::read(picture::path(media, name))?)?;
    }
    zip.finish()?;
    Ok(())
}

/// Reads a package of Electrip 2 or 1 and saves the picture in the media
/// directory `media`; a picture that cannot be read is left out and named in
/// the report.
pub fn read(path: &Path, media: &Path) -> Result<Package, ImportError> {
    let file = File::open(path).map_err(read_error)?;
    let mut zip = ZipArchive::new(file).map_err(read_error)?;
    let mut report = Vec::new();
    let (mut loco, actions, picture) = if zip.index_for_name(CONTENT).is_some() {
        let content: Content = serde_json::from_slice(&entry(&mut zip, CONTENT)?)
            .map_err(|e| ImportError::Invalid(e.to_string()))?;
        let picture = content.loco.picture().map(media_entry);
        (content.loco, content.actions, picture)
    } else {
        let name = zip
            .file_names()
            .flatten()
            .find(|n| n.ends_with(".loco") && !n.contains('/'))
            .ok_or(ImportError::Invalid("no loco file".into()))?
            .into_owned();
        let (loco, actions, picture) = electrip1::loco(&entry(&mut zip, &name)?, &mut report)?;
        let picture = picture.map(|p| p.to_string_lossy().into_owned());
        (loco, actions, picture)
    };
    let stored = picture.and_then(|name| match store_picture(&mut zip, &name, media) {
        Ok(stored) => Some(stored),
        Err(error) => {
            report.push(format!("{}: {error} ({name})", loco.name()));
            None
        }
    });
    loco.set_picture(stored);
    Ok(Package {
        loco,
        actions,
        report,
    })
}

/// Saves the picture `name` of the archive in the media directory.
fn store_picture(zip: &mut ZipArchive<File>, name: &str, media: &Path) -> Result<String, String> {
    let bytes = entry(zip, name).map_err(|e| e.to_string())?;
    picture::store_bytes(media, &bytes, None).map_err(|e| e.to_string())
}

fn media_entry(name: &str) -> String {
    format!("media/{name}.png")
}

/// The content of the file `name` in the archive.
fn entry(zip: &mut ZipArchive<File>, name: &str) -> Result<Vec<u8>, ImportError> {
    let mut bytes = Vec::new();
    zip.by_name(name)
        .map_err(read_error)?
        .read_to_end(&mut bytes)
        .map_err(read_error)?;
    Ok(bytes)
}

fn read_error(error: impl ToString) -> ImportError {
    ImportError::Read(error.to_string())
}

#[cfg(test)]
mod tests;
