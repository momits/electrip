//! `cargo xtask corpus [--record]`: checks that every file in `tests/corpus/`
//! matches `tests/corpus/SHA256SUMS` and that the configurations in
//! `configs/` are what `tools/legacy-harness/corpus.py` makes from the loco
//! packages. `--record` rewrites the configurations and `SHA256SUMS`.

use crate::golden::python;
use crate::{Result, root};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};

pub fn corpus(flag: Option<&str>) -> Result {
    let record = match flag {
        None => false,
        Some("--record") => true,
        _ => return Err("usage: cargo xtask corpus [--record]".into()),
    };
    let dir = root().join("tests/corpus");
    let configs = dir.join("configs");
    let out = if record {
        configs.clone()
    } else {
        let out = root().join("target/corpus");
        let _ = fs::remove_dir_all(&out);
        out
    };
    fs::create_dir_all(&out).map_err(|e| format!("{}: {e}", out.display()))?;
    python("corpus.py", &[&dir.join("packages"), &out])?;

    let sums_path = dir.join("SHA256SUMS");
    let sums = sha256sums(&dir)?;
    if record {
        fs::write(&sums_path, sums).map_err(|e| format!("{}: {e}", sums_path.display()))?;
        println!("ok    corpus recorded");
        return Ok(());
    }
    let (committed, fresh) = (files(&configs)?, files(&out)?);
    if committed.len() != fresh.len() {
        return Err("corpus: configs/ and the output of corpus.py have different files".into());
    }
    for (config, new) in committed.iter().zip(&fresh) {
        if config.file_name() != new.file_name() || read(config)? != read(new)? {
            return Err(format!(
                "corpus: {} differs from corpus.py",
                config.display()
            ));
        }
    }
    let expected =
        fs::read_to_string(&sums_path).map_err(|e| format!("{}: {e}", sums_path.display()))?;
    if expected != sums {
        let line = sums
            .lines()
            .zip(expected.lines())
            .take_while(|(a, b)| a == b)
            .count()
            + 1;
        return Err(format!(
            "corpus: SHA256SUMS differs from the files at line {line}"
        ));
    }
    println!("ok    corpus");
    Ok(())
}

/// One line `<hash>  <path>` per file, the format of `sha256sum`.
fn sha256sums(dir: &Path) -> Result<String> {
    let mut sums = String::new();
    for path in files(dir)? {
        let name = path.strip_prefix(dir).unwrap_or(&path).to_string_lossy();
        if name != "SHA256SUMS" {
            let hex = format!("{:x}", Sha256::digest(read(&path)?));
            sums.push_str(&format!("{hex}  {}\n", name.replace('\\', "/")));
        }
    }
    Ok(sums)
}

/// All files below `dir`, sorted.
fn files(dir: &Path) -> Result<Vec<PathBuf>> {
    let mut found = Vec::new();
    for entry in fs::read_dir(dir).map_err(|e| format!("{}: {e}", dir.display()))? {
        let path = entry.map_err(|e| e.to_string())?.path();
        if path.is_dir() {
            found.extend(files(&path)?);
        } else {
            found.push(path);
        }
    }
    found.sort();
    Ok(found)
}

fn read(path: &Path) -> Result<Vec<u8>> {
    fs::read(path).map_err(|e| format!("{}: {e}", path.display()))
}
