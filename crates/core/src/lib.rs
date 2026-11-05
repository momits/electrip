//! Domain model and command engine of Electrip 2.
//!
//! Every user action is a command handled here (ADR 0002). This crate must not
//! depend on any other crate of the workspace.

pub mod config;
pub mod decoder;
pub mod drive;
pub mod electrip1;
pub mod function;
pub mod host;
pub mod input;
pub mod loco;
pub mod package;
pub mod picture;
pub mod session;
pub mod sound;
pub mod speed_curve;
pub mod station;
