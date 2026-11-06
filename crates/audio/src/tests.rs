use std::fs;
use std::path::{Path, PathBuf};

use super::{Source, open};

fn corpus_package(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/corpus/packages")
        .join(name)
}

/// Unpacks one sound of a corpus package into `dir`.
pub(crate) fn extract(dir: &Path, package: &str, sound: &str) -> PathBuf {
    let mut archive =
        zip::ZipArchive::new(fs::File::open(corpus_package(package)).unwrap()).unwrap();
    let path = dir.join("sound");
    let mut entry = archive.by_name(&format!("sound/{sound}")).unwrap();
    std::io::copy(&mut entry, &mut fs::File::create(&path).unwrap()).unwrap();
    path
}

/// Unpacks one sound of a corpus package and returns its decoded format.
fn decode(package: &str, sound: &str) -> (u32, u16, usize) {
    let dir = tempfile::tempdir().unwrap();
    let decoder = open(&extract(dir.path(), package, sound)).unwrap();
    let (rate, channels) = (decoder.sample_rate().get(), decoder.channels().get());
    (rate, channels, decoder.count())
}

#[test]
fn wav_and_ogg_are_decoded_at_the_sample_rate_of_the_file() {
    let cases = [
        ("BR 216.zip", "Horn BR216.wav", 22_050, 1),
        ("BR 216.zip", "18 - abstellen2.wav", 44_100, 2),
        ("V 60.zip", "horn.ogg", 44_100, 1),
        ("BR 216.zip", "02 - leerlauf.ogg", 44_100, 2),
    ];
    for (package, sound, rate, channels) in cases {
        let (got_rate, got_channels, samples) = decode(package, sound);
        assert_eq!((got_rate, got_channels), (rate, channels), "{sound}");
        assert!(samples > 0, "{sound} has no samples");
    }
}

#[test]
fn every_sound_of_the_corpus_is_decoded() {
    for entry in fs::read_dir(corpus_package("")).unwrap() {
        let package = entry.unwrap().file_name().into_string().unwrap();
        let file = fs::File::open(corpus_package(&package)).unwrap();
        let archive = zip::ZipArchive::new(file).unwrap();
        let sounds: Vec<String> = archive
            .file_names()
            .filter_map(|n| Some(n.ok()?.strip_prefix("sound/")?.to_string()))
            .filter(|n| n.ends_with(".wav") || n.ends_with(".ogg"))
            .collect();
        for sound in sounds {
            assert!(decode(&package, &sound).2 > 0, "{package}: {sound}");
        }
    }
}

#[test]
fn a_file_that_is_no_sound_is_an_error() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("broken.ogg");
    fs::write(&path, b"not a sound").unwrap();
    assert!(open(&path).err().unwrap().starts_with("cannot decode"));
    assert!(
        open(&dir.path().join("missing.wav"))
            .err()
            .unwrap()
            .starts_with("cannot open")
    );
}
