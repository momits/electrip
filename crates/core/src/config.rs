//! Configurations (B-21): the part of a session that is saved. The library
//! is a directory with one JSON file `<name>.json` per configuration.

use crate::function::Action;
use crate::input::Mapping;
use crate::loco::Loco;
use crate::session::Station;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

/// Name of the configuration a new library starts with.
pub const DEFAULT_NAME: &str = "Electrip";

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub locos: Vec<Loco>,
    pub actions: Vec<Action>,
    pub mappings: Vec<Mapping>,
    pub station: Station,
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

/// The file of the configuration `name` in the library `dir`.
pub fn path(dir: &Path, name: &str) -> PathBuf {
    dir.join(format!("{name}.json"))
}

/// The names of the configurations in the library, sorted.
pub fn names(dir: &Path) -> io::Result<Vec<String>> {
    let mut names = Vec::new();
    for entry in fs::read_dir(dir)? {
        let path = entry?.path();
        if path.extension().is_some_and(|e| e == "json") {
            names.extend(path.file_stem().and_then(|s| s.to_str()).map(String::from));
        }
    }
    names.sort();
    Ok(names)
}

pub fn read(path: &Path) -> io::Result<Config> {
    let json = fs::read_to_string(path)?;
    serde_json::from_str(&json).map_err(io::Error::other)
}

pub fn write(path: &Path, config: &Config) -> io::Result<()> {
    let json = serde_json::to_string_pretty(config).map_err(io::Error::other)?;
    fs::write(path, json)
}

#[cfg(test)]
mod tests;
