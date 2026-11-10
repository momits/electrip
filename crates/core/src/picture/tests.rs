use super::*;
use image::{Rgb, RgbImage};
use tempfile::TempDir;

const RED: Rgb<u8> = Rgb([255, 0, 0]);
const BLUE: Rgb<u8> = Rgb([0, 0, 255]);

/// An image of `width`×`height`, red left of `split` and blue right of it.
fn image_file(dir: &Path, name: &str, width: u32, height: u32, split: u32) -> PathBuf {
    let image = RgbImage::from_fn(width, height, |x, _| if x < split { RED } else { BLUE });
    let path = dir.join(name);
    image.save(&path).unwrap();
    path
}

fn saved(dir: &Path, name: &str) -> RgbImage {
    image::open(path(dir, name)).unwrap().to_rgb8()
}

#[test]
fn the_centered_crop_is_the_largest_in_the_middle() {
    let wide = Crop::centered(1000, 340);
    assert_eq!(
        wide,
        Crop {
            x: 280,
            y: 0,
            width: 440
        }
    );
    let tall = Crop::centered(440, 1000);
    assert_eq!(
        tall,
        Crop {
            x: 0,
            y: 330,
            width: 440
        }
    );
    assert_eq!(Crop::centered(220, 170).width, 220);
}

#[test]
fn the_crop_is_saved_in_the_fixed_size() {
    let dir = TempDir::new().unwrap();
    let source = image_file(dir.path(), "lok.png", 300, 100, 150);
    let crop = Crop {
        x: 160,
        y: 10,
        width: 110,
    };
    let name = store(dir.path(), &source, Some(crop)).unwrap();
    let picture = saved(dir.path(), &name);
    assert_eq!(picture.dimensions(), (WIDTH, HEIGHT));
    assert!(picture.pixels().all(|p| *p == BLUE));
}

#[test]
fn by_default_the_middle_is_saved() {
    let dir = TempDir::new().unwrap();
    // Red only in the stripes left and right of the middle crop.
    let source = image_file(dir.path(), "lok.jpg", 1000, 340, 280);
    let name = store(dir.path(), &source, None).unwrap();
    let picture = saved(dir.path(), &name);
    // JPEG is lossy; the left edge blends with red.
    assert!(picture.get_pixel(WIDTH / 2, HEIGHT / 2).0[2] > 200);
    assert!(picture.get_pixel(WIDTH - 1, 0).0[0] < 50);
}

#[test]
fn the_same_picture_is_saved_once() {
    let dir = TempDir::new().unwrap();
    let source = image_file(dir.path(), "lok.png", 440, 340, 100);
    let first = store(dir.path(), &source, None).unwrap();
    let second = store(dir.path(), &source, None).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.len(), 64);
    assert_eq!(
        fs::read_dir(dir.path().join(media::PICTURES))
            .unwrap()
            .count(),
        1
    );
}

#[test]
fn the_crop_must_lie_inside_the_image() {
    let dir = TempDir::new().unwrap();
    let source = image_file(dir.path(), "lok.png", 440, 340, 100);
    for crop in [
        Crop {
            x: 1,
            y: 0,
            width: 440,
        },
        Crop {
            x: 0,
            y: 1,
            width: 440,
        },
        Crop {
            x: 0,
            y: 0,
            width: 0,
        },
        Crop {
            x: u32::MAX,
            y: 0,
            width: 10,
        },
    ] {
        let result = store(dir.path(), &source, Some(crop));
        assert_eq!(result, Err(PictureError::CropOutsideImage), "{crop:?}");
    }
}

#[test]
fn files_that_are_no_images_cannot_be_read() {
    let dir = TempDir::new().unwrap();
    let source = dir.path().join("lok.png");
    fs::write(&source, "kein Bild").unwrap();
    let result = store(dir.path(), &source, None);
    assert!(matches!(result, Err(PictureError::Read(_))), "{result:?}");
}
