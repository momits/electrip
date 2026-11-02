//! Loco pictures (B-05): a crop of any PNG or JPEG in the aspect ratio of
//! Electrip 1 (110×85 px), saved in a fixed resolution. The media
//! directory holds each picture once, named by its SHA-256 (ADR 0003).

use image::imageops::FilterType;
use image::{GenericImageView, ImageFormat};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::fmt;
use std::fs;
use std::io::Cursor;
use std::path::{Path, PathBuf};

/// Size of a saved picture, 4 times that of Electrip 1 for high resolution
/// screens.
pub const WIDTH: u32 = 440;
pub const HEIGHT: u32 = 340;

/// The crop of the loaded image in its pixels: top left corner and width;
/// the height follows from the aspect ratio. Moving the corner pans,
/// a smaller width zooms in.
#[derive(Debug, Clone, Copy, PartialEq, Deserialize)]
pub struct Crop {
    pub x: u32,
    pub y: u32,
    pub width: u32,
}

impl Crop {
    /// The largest crop in the middle of an image of `width`×`height`.
    pub fn centered(width: u32, height: u32) -> Crop {
        let crop_width = width.min(height_to_width(height));
        let crop_height = width_to_height(crop_width);
        Crop {
            x: (width - crop_width) / 2,
            y: (height - crop_height) / 2,
            width: crop_width,
        }
    }

    fn height(&self) -> u32 {
        width_to_height(self.width)
    }
}

fn width_to_height(width: u32) -> u32 {
    (u64::from(width) * u64::from(HEIGHT) / u64::from(WIDTH)) as u32
}

fn height_to_width(height: u32) -> u32 {
    (u64::from(height) * u64::from(WIDTH) / u64::from(HEIGHT)) as u32
}

#[derive(Debug, Clone, PartialEq)]
pub enum PictureError {
    Read(String),
    CropOutsideImage,
    Write(String),
}

impl fmt::Display for PictureError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            PictureError::Read(reason) => write!(f, "cannot read the picture: {reason}"),
            PictureError::CropOutsideImage => f.write_str("the crop must lie inside the picture"),
            PictureError::Write(reason) => write!(f, "cannot save the picture: {reason}"),
        }
    }
}

/// The file of the picture `name` in the media directory `dir`.
pub fn path(dir: &Path, name: &str) -> PathBuf {
    dir.join(format!("{name}.png"))
}

/// Saves the crop of the image at `source` in the media directory `dir`,
/// by default the largest one in the middle; returns the picture's name.
pub fn store(dir: &Path, source: &Path, crop: Option<Crop>) -> Result<String, PictureError> {
    let image = image::open(source).map_err(|e| PictureError::Read(e.to_string()))?;
    let (width, height) = image.dimensions();
    let crop = crop.unwrap_or(Crop::centered(width, height));
    let inside = crop.width > 0
        && crop.height() > 0
        && u64::from(crop.x) + u64::from(crop.width) <= u64::from(width)
        && u64::from(crop.y) + u64::from(crop.height()) <= u64::from(height);
    if !inside {
        return Err(PictureError::CropOutsideImage);
    }
    let mut png = Vec::new();
    image
        .crop_imm(crop.x, crop.y, crop.width, crop.height())
        .resize_exact(WIDTH, HEIGHT, FilterType::Lanczos3)
        .write_to(&mut Cursor::new(&mut png), ImageFormat::Png)
        .map_err(|e| PictureError::Write(e.to_string()))?;
    let name: String = Sha256::digest(&png)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect();
    let write = || -> std::io::Result<()> {
        fs::create_dir_all(dir)?;
        fs::write(path(dir, &name), &png)
    };
    write().map_err(|e| PictureError::Write(e.to_string()))?;
    Ok(name)
}

#[cfg(test)]
mod tests;
