//! Sound files of Electrip 2. WAV and OGG are played at the sample rate
//! stored in the file; there is no sample rate setting (B-18).

use std::fs::File;
use std::io::BufReader;
use std::path::Path;

pub use rodio::{Decoder, Source};

/// Opens a WAV or OGG file as a stream of samples.
pub fn open(path: &Path) -> Result<Decoder<BufReader<File>>, String> {
    let file = File::open(path).map_err(|e| format!("cannot open {}: {e}", path.display()))?;
    Decoder::try_from(file).map_err(|e| format!("cannot decode {}: {e}", path.display()))
}

#[cfg(test)]
mod tests;
