//! Loco packages (B-20): a loco with its picture and sounds as a ZIP archive.
//! Electrip 2 writes `loco.json` with the loco and the actions its functions
//! and sound functions use, the picture as `media/<name>.png` and each sound
//! as `sounds/<name>` named by its content. A package of Electrip 1 holds
//! `<name>.loco` and the files it names.

use crate::electrip1::{self, ImportError};
use crate::function::Action;
use crate::loco::Loco;
use crate::media;
use crate::picture;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use zip::write::SimpleFileOptions;
use zip::{ZipArchive, ZipWriter};

const CONTENT: &str = "loco.json";

#[derive(Debug, Clone, PartialEq)]
pub struct Package {
    /// Its picture and sounds are already in the library.
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
/// sounds use, its picture and its sound files from the `library` to a
/// package at `path`.
pub fn write(path: &Path, loco: &Loco, actions: &[Action], library: &Path) -> io::Result<()> {
    let used = |a: &&Action| {
        let sounds = loco.sound_functions().iter().map(|f| f.action);
        let events = loco.event_sounds().iter().map(|s| s.action);
        let functions = loco.functions().iter().map(|f| f.action);
        let mut ids = functions.chain(sounds).chain(events);
        ids.any(|id| id == a.id)
    };
    let mut content = Content {
        loco: loco.clone(),
        actions: actions.iter().filter(used).cloned().collect(),
    };
    let sounds = pack_sounds(&mut content.loco, library)?;
    let mut zip = ZipWriter::new(File::create(path)?);
    zip.start_file(CONTENT, SimpleFileOptions::default())?;
    serde_json::to_writer_pretty(&mut zip, &content)?;
    for (name, bytes) in sounds {
        zip.start_file(name, SimpleFileOptions::default())?;
        zip.write_all(&bytes)?;
    }
    if let Some(name) = loco.picture() {
        zip.start_file(media::picture_path(name), SimpleFileOptions::default())?;
        zip.write_all(&fs::read(picture::path(library, name))?)?;
    }
    zip.finish()?;
    Ok(())
}

/// Points the sounds of the loco to their entries in the archive and
/// returns the entries with their content.
fn pack_sounds(loco: &mut Loco, library: &Path) -> io::Result<BTreeMap<String, Vec<u8>>> {
    let mut sounds = BTreeMap::new();
    let mut error = None;
    loco.map_sounds(|path| match fs::read(media::file(library, path)) {
        Ok(bytes) => {
            let name = media::sound_path(&bytes, path);
            sounds.insert(name.clone(), bytes);
            Some(name.into())
        }
        Err(e) => {
            error.get_or_insert(e);
            None
        }
    });
    error.map_or(Ok(sounds), Err)
}

/// Reads a package of Electrip 2 or 1 and saves the picture and the sounds
/// in the `library`; a file that cannot be read is left out and named in
/// the report.
pub fn read(path: &Path, library: &Path) -> Result<Package, ImportError> {
    let file = File::open(path).map_err(read_error)?;
    let mut zip = ZipArchive::new(file).map_err(read_error)?;
    let mut report = Vec::new();
    let (mut loco, actions, picture) = if zip.index_for_name(CONTENT).is_some() {
        let content: Content = serde_json::from_slice(&entry(&mut zip, CONTENT)?)
            .map_err(|e| ImportError::Invalid(e.to_string()))?;
        let picture = content.loco.picture().map(media::picture_path);
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
    let stored = picture.and_then(|name| match store_picture(&mut zip, &name, library) {
        Ok(stored) => Some(stored),
        Err(error) => {
            report.push(format!("{}: {error} ({name})", loco.name()));
            None
        }
    });
    loco.set_picture(stored);
    let name = loco.name().to_owned();
    loco.map_sounds(|path| match store_sound(&mut zip, path, library) {
        Ok(stored) => Some(stored),
        Err(error) => {
            report.push(format!("{name}: {error} ({})", path.display()));
            None
        }
    });
    Ok(Package {
        loco,
        actions,
        report,
    })
}

/// Saves the picture `name` of the archive in the library.
fn store_picture(zip: &mut ZipArchive<File>, name: &str, library: &Path) -> Result<String, String> {
    let bytes = entry(zip, name).map_err(|e| e.to_string())?;
    picture::store_bytes(library, &bytes, None).map_err(|e| e.to_string())
}

/// Saves the sound `name` of the archive in the library.
fn store_sound(zip: &mut ZipArchive<File>, name: &Path, library: &Path) -> Result<PathBuf, String> {
    let bytes = entry(zip, &name.to_string_lossy()).map_err(|e| e.to_string())?;
    media::add_sound(library, &bytes, name).map_err(|e| e.to_string())
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
