//! Logical actions (N-07) and the decoder functions a loco maps them to
//! (B-07). Input devices trigger actions; each loco decides what an action
//! switches.

use serde::{Deserialize, Serialize};

/// A named action of the configuration, the same for all locos.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Action {
    pub id: u32,
    pub name: String,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Mode {
    /// The first trigger switches on, the second off.
    #[default]
    Switch,
    /// On while the action is held.
    Push,
}

/// A decoder function `number` that the action `action` switches.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Function {
    pub action: u32,
    pub number: u8,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub mode: Mode,
    /// Inverts both modes: the function is on until triggered.
    #[serde(default)]
    pub default_on: bool,
    /// Whether the function is on now; starts with `default_on`.
    #[serde(skip_deserializing)]
    pub on: bool,
}

impl Function {
    /// Reacts to pressing (`pressed`) or releasing the action.
    pub fn trigger(&mut self, pressed: bool) {
        match self.mode {
            Mode::Switch => self.on ^= pressed,
            Mode::Push => self.on = pressed != self.default_on,
        }
    }
}

#[cfg(test)]
mod tests;
