//! Domain model and command engine of Electrip 2.
//!
//! Every user action is a command handled here (ADR 0002). This crate must not
//! depend on any other crate of the workspace.

pub mod decoder;
pub mod drive;
pub mod loco;
pub mod session;
pub mod speed_curve;
pub mod station;
