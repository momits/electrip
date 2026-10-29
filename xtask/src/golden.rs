//! `cargo xtask golden [--record]`: runs every scenario in
//! `tests/golden/scenarios/` through the Electrip 1 harness
//! (`tools/legacy-harness/`) and checks or rewrites `tests/golden/<name>.jsonl`.

use crate::{Result, root};
use std::fs;
use std::path::Path;
use std::process::Command;

pub fn golden(flag: Option<&str>) -> Result {
    let record = match flag {
        None => false,
        Some("--record") => true,
        _ => return Err("usage: cargo xtask golden [--record]".into()),
    };
    let dir = root().join("tests/golden");
    let mut scenarios: Vec<_> = fs::read_dir(dir.join("scenarios"))
        .map_err(|e| format!("tests/golden/scenarios: {e}"))?
        .filter_map(|entry| entry.ok().map(|e| e.path()))
        .filter(|path| path.extension().is_some_and(|ext| ext == "json"))
        .collect();
    scenarios.sort();
    for scenario in &scenarios {
        let name = scenario.file_stem().and_then(|s| s.to_str()).unwrap_or("?");
        let output = run_harness(scenario)?;
        let golden = dir.join(format!("{name}.jsonl"));
        if record {
            fs::write(&golden, output).map_err(|e| format!("{}: {e}", golden.display()))?;
            println!("ok    golden recorded {name}");
        } else {
            let expected = fs::read_to_string(&golden).map_err(|_| {
                format!("golden {name}: missing {name}.jsonl, run cargo xtask golden --record")
            })?;
            if let Some(line) = first_difference(&expected, &output) {
                return Err(format!(
                    "golden {name}: harness output differs from {name}.jsonl at line {line}"
                ));
            }
            println!("ok    golden {name}");
        }
    }
    Ok(())
}

fn run_harness(scenario: &Path) -> Result<String> {
    let out = Command::new("python3")
        .arg(root().join("tools/legacy-harness/harness.py"))
        .arg(scenario)
        .output()
        .map_err(|e| format!("python3: {e}"))?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        return Err(format!("harness {}: {}", scenario.display(), err.trim()));
    }
    String::from_utf8(out.stdout).map_err(|e| e.to_string())
}

/// 1-based number of the first differing line, if any.
fn first_difference(expected: &str, actual: &str) -> Option<usize> {
    if expected == actual {
        return None;
    }
    let same = expected
        .lines()
        .zip(actual.lines())
        .take_while(|(a, b)| a == b);
    Some(same.count() + 1)
}
