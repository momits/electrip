//! Configurations (B-21): the part of a session that is saved. The library
//! is a directory with one JSON file `<name>.json` per configuration.

use crate::function::Action;
use crate::input::Mapping;
use crate::loco::Loco;
use crate::session::Station;
use serde::{Deserialize, Serialize};
use std::collections::hash_map::RandomState;
use std::fs;
use std::hash::BuildHasher;
use std::io;
use std::path::{Path, PathBuf};

/// Name of the configuration a new library starts with.
pub const DEFAULT_NAME: &str = "Electrip";

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    /// Stays the same when the configuration is renamed or copied to
    /// another instance, so that copies can be merged (N-04).
    pub id: String,
    pub locos: Vec<Loco>,
    pub actions: Vec<Action>,
    pub mappings: Vec<Mapping>,
    pub station: Station,
    pub view: View,
}

/// Options of the control view (B-22).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct View {
    /// Brings the new loco of a device into view when it changes locos.
    pub auto_focus: bool,
    /// Shows only the locos a device controls or that are moving.
    pub only_active: bool,
}

/// Auto-focus is on, like in Electrip 1.
impl Default for View {
    fn default() -> Self {
        View {
            auto_focus: true,
            only_active: false,
        }
    }
}

/// Characters that are not allowed in file names on some platform.
const FORBIDDEN: &[char] = &['<', '>', ':', '"', '/', '\\', '|', '?', '*'];

/// Whether `name` can name a configuration file on every platform.
pub fn valid_name(name: &str) -> bool {
    !name.is_empty()
        && !name.starts_with('.')
        && !name.ends_with(' ')
        && !name.contains(|c: char| c.is_control() || FORBIDDEN.contains(&c))
}

/// A new, random configuration id.
pub fn new_id() -> String {
    format!("{:016x}", RandomState::new().hash_one(()))
}

/// The file of the configuration `name` in the library `dir`.
pub fn path(dir: &Path, name: &str) -> PathBuf {
    dir.join(format!("{name}.json"))
}

/// The names of the configurations in the library, sorted; files whose
/// names are no valid names are left out.
pub fn names(dir: &Path) -> io::Result<Vec<String>> {
    let mut names = Vec::new();
    for entry in fs::read_dir(dir)? {
        let path = entry?.path();
        if path.extension().is_some_and(|e| e == "json") {
            let name = path.file_stem().and_then(|s| s.to_str());
            names.extend(name.filter(|n| valid_name(n)).map(String::from));
        }
    }
    names.sort();
    Ok(names)
}

/// Reads a configuration; one without an id (from before N-04) gets one.
pub fn read(path: &Path) -> io::Result<Config> {
    let json = fs::read_to_string(path)?;
    let mut config: Config = serde_json::from_str(&json).map_err(io::Error::other)?;
    if config.id.is_empty() {
        config.id = new_id();
        write(path, &config)?;
    }
    Ok(config)
}

/// Writes a temporary file first, so a crash cannot leave half a file.
pub fn write(path: &Path, config: &Config) -> io::Result<()> {
    let json = serde_json::to_string_pretty(config).map_err(io::Error::other)?;
    let temporary = path.with_extension("json.tmp");
    fs::write(&temporary, json)?;
    fs::rename(temporary, path)
}

#[cfg(test)]
mod tests;
