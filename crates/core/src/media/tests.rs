use super::*;
use crate::decoder::{Decoder, Protocol};
use crate::function_sound::SoundFunction;
use crate::loco::Loco;
use tempfile::TempDir;

#[test]
fn a_sound_is_named_by_its_content_with_its_extension() {
    let library = TempDir::new().unwrap();
    let path = add_sound(library.path(), b"tuut", Path::new("/x/horn.ogg")).unwrap();
    let name = format!("{}.ogg", content_name(b"tuut"));
    assert_eq!(path, Path::new("sounds").join(name));
    assert_eq!(fs::read(library.path().join(&path)).unwrap(), b"tuut");
}

#[test]
fn a_file_goes_to_another_library_under_the_same_path() {
    let (a, b) = (TempDir::new().unwrap(), TempDir::new().unwrap());
    let path = add_sound(a.path(), b"tuut", Path::new("horn.ogg")).unwrap();
    let path = path.to_str().unwrap();

    write(b.path(), path, &read(a.path(), path).unwrap()).unwrap();

    assert_eq!(read(b.path(), path).unwrap(), b"tuut");
}

#[test]
fn only_pictures_and_sounds_are_read() {
    let library = TempDir::new().unwrap();
    let hash = content_name(b"");
    for path in ["../lok", "config/x.json", &format!("sounds/{hash}.o/g")] {
        let error = read(library.path(), path).unwrap_err();
        assert_eq!(
            error.to_string(),
            format!("there is no picture or sound {path}")
        );
    }
}

#[test]
fn a_file_is_only_written_under_its_content_name() {
    let library = TempDir::new().unwrap();
    let path = format!("sounds/{}.ogg", content_name(b"tuut"));
    let error = write(library.path(), &path, b"other").unwrap_err();
    assert_eq!(error.to_string(), format!("the content is not {path}"));
    assert!(!library.path().join(path).exists());
}

#[test]
fn the_files_of_the_library_that_are_not_there_are_missing() {
    let library = TempDir::new().unwrap();
    let there = add_sound(library.path(), b"da", Path::new("a.ogg")).unwrap();
    let absent = format!("sounds/{}.ogg", content_name(b"weg"));
    let decoder = Decoder::new(Protocol::DccShort, 3, 128).unwrap();
    let mut loco = Loco::new(decoder, 100.0).unwrap();
    loco.set_picture(Some(content_name(b"bild")));
    let sounds = [there, absent.clone().into(), "/elsewhere/b.ogg".into()];
    *loco.sound_functions_mut() = sounds
        .into_iter()
        .map(|path| SoundFunction {
            path: Some(path),
            ..SoundFunction::default()
        })
        .collect();
    let config = Config {
        locos: vec![loco.clone(), loco],
        ..Config::default()
    };

    let picture = format!("media/{}.png", content_name(b"bild"));
    assert_eq!(missing(library.path(), &config), [picture, absent]);
}

#[test]
fn a_sound_of_the_library_plays_from_there() {
    let library = Path::new("/lib");
    let sound = format!("sounds/{}.ogg", content_name(b""));
    assert_eq!(file(library, Path::new(&sound)), library.join(&sound));
    assert_eq!(file(library, Path::new("horn")), Path::new("horn"));
}
