//! Project automation: `cargo xtask <command>`. See AGENTS.md.

mod golden;
mod sim;

use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use std::{env, fs};

/// Maximum lines of product code (ADR 0006).
const LOC_BUDGET: usize = 12_000;

/// Allowed workspace dependencies per crate (layer rule in AGENTS.md).
/// `None` means the crate may depend on every workspace crate.
const LAYERS: &[(&str, Option<&[&str]>)] = &[
    ("electrip-core", Some(&[])),
    ("electrip-station-srcp", Some(&["electrip-core"])),
    ("electrip-station-z21", Some(&["electrip-core"])),
    ("electrip-input", Some(&["electrip-core"])),
    ("electrip-audio", Some(&["electrip-core"])),
    ("electrip-library", Some(&["electrip-core"])),
    ("electrip-sync", Some(&["electrip-core"])),
    ("electrip-control", None),
    ("electrip", None),
    ("xtask", Some(&[])),
];

type Result<T = ()> = std::result::Result<T, String>;

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    let result = match args.first().map(String::as_str) {
        Some("test") => test(),
        Some("loc") => loc(),
        Some("parity") => parity(),
        Some("review-check") => review_check(args.get(1).map(String::as_str)),
        Some("sim") => sim::sim(args.get(1).map(String::as_str)),
        Some("golden") => golden::golden(args.get(1).map(String::as_str)),
        _ => Err("usage: cargo xtask <test | loc | parity | review-check [base] | sim up|down | golden [--record]>".into()),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("ERROR {e}");
            ExitCode::FAILURE
        }
    }
}

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_default()
}

/// fmt, clippy, layer rule and tests; full output goes to `target/test-logs/`.
fn test() -> Result {
    run_logged("fmt", &["fmt", "--all", "--", "--check"])?;
    run_logged(
        "clippy",
        &[
            "clippy",
            "--workspace",
            "--all-targets",
            "--",
            "-D",
            "warnings",
        ],
    )?;
    layers()?;
    println!("ok    layers");
    run_logged("test", &["test", "--workspace"])
}

/// Runs a cargo command, writes its output to a log file and prints only the
/// tail of the log on failure.
fn run_logged(step: &str, args: &[&str]) -> Result {
    let out = Command::new("cargo")
        .args(args)
        .current_dir(root())
        .output()
        .map_err(|e| format!("{step}: cannot start cargo: {e}"))?;
    let log_dir = root().join("target/test-logs");
    fs::create_dir_all(&log_dir).map_err(|e| e.to_string())?;
    let log = log_dir.join(format!("{step}.log"));
    let text = [out.stdout, out.stderr].concat();
    fs::write(&log, &text).map_err(|e| e.to_string())?;
    if out.status.success() {
        println!("ok    {step}");
        return Ok(());
    }
    let text = String::from_utf8_lossy(&text);
    let tail: Vec<&str> = text.lines().rev().take(20).collect();
    for line in tail.iter().rev() {
        eprintln!("{line}");
    }
    Err(format!("{step} failed, full log: {}", log.display()))
}

fn layers() -> Result {
    let out = Command::new("cargo")
        .args(["metadata", "--format-version", "1", "--no-deps"])
        .current_dir(root())
        .output()
        .map_err(|e| format!("cargo metadata: {e}"))?;
    let meta: Value =
        serde_json::from_slice(&out.stdout).map_err(|e| format!("cargo metadata: {e}"))?;
    let packages = meta["packages"].as_array().cloned().unwrap_or_default();
    let members: Vec<&str> = packages.iter().filter_map(|p| p["name"].as_str()).collect();
    let mut errors = Vec::new();
    for package in &packages {
        let name = package["name"].as_str().unwrap_or("?");
        let Some((_, allowed)) = LAYERS.iter().find(|(n, _)| *n == name) else {
            errors.push(format!("{name} is missing in LAYERS (xtask/src/main.rs)"));
            continue;
        };
        let deps = package["dependencies"].as_array().into_iter().flatten();
        for dep in deps.filter_map(|d| d["name"].as_str()) {
            if members.contains(&dep) && allowed.is_some_and(|a| !a.contains(&dep)) {
                errors.push(format!("{name} must not depend on {dep}"));
            }
        }
    }
    if errors.is_empty() {
        Ok(())
    } else {
        Err(format!("layers: {}", errors.join("; ")))
    }
}

fn loc() -> Result {
    let mut total = 0;
    count_lines(&root().join("crates"), &mut total)?;
    println!("loc   {total} / {LOC_BUDGET} lines of product code");
    if total > LOC_BUDGET {
        return Err(format!("loc: budget exceeded by {}", total - LOC_BUDGET));
    }
    Ok(())
}

/// Counts non-blank, non-comment lines of `.rs` files, skipping test code
/// (`tests/` directories and `tests.rs` files, see AGENTS.md).
fn count_lines(dir: &Path, total: &mut usize) -> Result {
    for entry in fs::read_dir(dir).map_err(|e| format!("{}: {e}", dir.display()))? {
        let path = entry.map_err(|e| e.to_string())?.path();
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        if path.is_dir() {
            if name != "tests" {
                count_lines(&path, total)?;
            }
        } else if name.ends_with(".rs") && name != "tests.rs" {
            let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
            *total += text
                .lines()
                .map(str::trim)
                .filter(|l| !l.is_empty() && !l.starts_with("//"))
                .count();
        }
    }
    Ok(())
}

/// Prints the parity report from `spec/requirements.json`
/// (W = wired, V = verified, A = accepted).
fn parity() -> Result {
    let path = root().join("spec/requirements.json");
    let text = fs::read_to_string(&path).map_err(|e| format!("{}: {e}", path.display()))?;
    let spec: Value = serde_json::from_str(&text).map_err(|e| format!("requirements.json: {e}"))?;
    let reqs = spec["requirements"].as_array().cloned().unwrap_or_default();
    let mut done = [0; 3];
    println!("id     phase W V A  title");
    for r in &reqs {
        let flags =
            ["wired", "verified", "accepted"].map(|k| r["status"][k].as_bool().unwrap_or(false));
        for (count, flag) in done.iter_mut().zip(flags) {
            *count += usize::from(flag);
        }
        let [w, v, a] = flags.map(|f| if f { "x" } else { "." });
        println!(
            "{:<6} {:<5} {w} {v} {a}  {}",
            r["id"].as_str().unwrap_or("?"),
            r["phase"].as_i64().unwrap_or(-1),
            r["title"].as_str().unwrap_or("")
        );
    }
    println!(
        "total {}: wired {}, verified {}, accepted {}",
        reqs.len(),
        done[0],
        done[1],
        done[2]
    );
    Ok(())
}

/// The newest commit in `base..HEAD` that touches `crates/` must carry the
/// trailer `Simplicity-Review: ok|refactored` (AGENTS.md, ADR 0008).
/// Without a usable base (first push) the whole history is checked.
fn review_check(base: Option<&str>) -> Result {
    let range = match base {
        Some(b) if !b.is_empty() && !b.chars().all(|c| c == '0') => format!("{b}..HEAD"),
        _ => "HEAD".to_string(),
    };
    let newest = git(&["log", "-1", "--format=%H", &range, "--", "crates/"])?;
    if newest.is_empty() {
        println!("ok    review-check (no product code changed)");
        return Ok(());
    }
    let trailer = git(&[
        "log",
        "-1",
        "--format=%(trailers:key=Simplicity-Review,valueonly)",
        &newest,
    ])?;
    match trailer.as_str() {
        "ok" | "refactored" => {
            println!("ok    review-check ({newest:.8}: {trailer})");
            Ok(())
        }
        _ => Err(format!(
            "review-check: commit {newest:.8} changes crates/ but lacks the trailer 'Simplicity-Review: ok|refactored'"
        )),
    }
}

fn git(args: &[&str]) -> Result<String> {
    let out = Command::new("git")
        .args(args)
        .current_dir(root())
        .output()
        .map_err(|e| format!("git: {e}"))?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        return Err(format!("git {}: {}", args.join(" "), err.trim()));
    }
    Ok(String::from_utf8_lossy(&out.stdout).trim().to_string())
}
