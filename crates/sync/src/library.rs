//! The documents of a library (N-04): the host keeps working on the JSON
//! files, the library keeps an Automerge document for each configuration
//! id in `sync/<id>.automerge` beside them, so that copies of a
//! configuration on other instances can be merged.

use crate::{Document, Error};
use electrip_core::config::{self, Config};
use std::fs;
use std::io::ErrorKind;
use std::path::{Path, PathBuf};

/// The ids of the configurations of the library and their names, to find
/// the ones another instance shares.
pub fn ids(library: &Path) -> Result<Vec<(String, String)>, Error> {
    let mut ids = Vec::new();
    for name in config::names(library)? {
        ids.push((config::read(&config::path(library, &name))?.id, name));
    }
    Ok(ids)
}

/// The document of the configuration `name`, with the changes of its
/// file since the last call.
pub fn document(library: &Path, name: &str) -> Result<Document, Error> {
    let config = config::read(&config::path(library, name))?;
    let mut document = stored(library, &config, || Document::new(&config))?;
    save(library, &config.id, &mut document)?;
    Ok(document)
}

/// Merges `other` into the configuration `name` and saves both; returns
/// whether the configuration changed. A configuration without a document
/// starts from `other`, since only documents with a common history merge
/// field by field.
pub fn merge(library: &Path, name: &str, other: &mut Document) -> Result<bool, Error> {
    let path = config::path(library, name);
    let config = config::read(&path)?;
    let mut document = stored(library, &config, || Document::load(&other.save()))?;
    document.merge(other)?;
    let merged = document.config()?;
    save(library, &merged.id, &mut document)?;
    if merged == config {
        return Ok(false);
    }
    config::write(&path, &merged)?;
    Ok(true)
}

/// Takes the configuration of `other`, named `name` on another instance,
/// into the library (N-03): merges it into the configuration with its id,
/// else saves it under `name` or, if that is taken, `name 2` and so on.
/// Returns its name in the library.
pub fn take(library: &Path, name: &str, other: &mut Document) -> Result<String, Error> {
    if !config::valid_name(name) {
        return Err(Error::InvalidId(name.into()));
    }
    fs::create_dir_all(library)?;
    let config = other.config()?;
    if let Some((_, known)) = ids(library)?.into_iter().find(|(id, _)| *id == config.id) {
        merge(library, &known, other)?;
        return Ok(known);
    }
    let (mut free, mut n) = (name.to_string(), 1);
    while config::path(library, &free).exists() {
        n += 1;
        free = format!("{name} {n}");
    }
    config::write(&config::path(library, &free), &config)?;
    merge(library, &free, other)?;
    Ok(free)
}

/// The saved document of `config` or else a new one, updated to `config`.
fn stored(
    library: &Path,
    config: &Config,
    new: impl FnOnce() -> Result<Document, Error>,
) -> Result<Document, Error> {
    let mut document = match fs::read(document_path(library, &config.id)?) {
        Ok(bytes) => Document::load(&bytes)?,
        Err(error) if error.kind() == ErrorKind::NotFound => new()?,
        Err(error) => return Err(error.into()),
    };
    document.update(config)?;
    Ok(document)
}

fn save(library: &Path, id: &str, document: &mut Document) -> Result<(), Error> {
    let path = document_path(library, id)?;
    fs::create_dir_all(library.join("sync"))?;
    let temporary = path.with_extension("automerge.tmp");
    fs::write(&temporary, document.save())?;
    fs::rename(temporary, path)?;
    Ok(())
}

/// Ids come from other instances, so they must not reach a file outside
/// the library.
fn document_path(library: &Path, id: &str) -> Result<PathBuf, Error> {
    if !config::valid_name(id) {
        return Err(Error::InvalidId(id.into()));
    }
    Ok(library.join("sync").join(format!("{id}.automerge")))
}

#[cfg(test)]
mod tests;
