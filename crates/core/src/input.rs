//! Input devices and their mappings (N-01, ADR 0009). Each device type
//! has a mapping from its controls (buttons, axes, hat directions) to
//! built-in actions (B-02) and logical actions (N-07). Controls are named
//! like SDL names them, e.g. `a`, `lefty` or `dpleft`.

use crate::drive::DEAD_ZONE;
use serde::{Deserialize, Serialize};

/// What a control does for the loco of its device.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Target {
    /// Accelerates with the axis (B-10); deflections up to `dead_zone`
    /// are ignored.
    Drive {
        #[serde(default = "default_dead_zone")]
        dead_zone: f64,
    },
    Reverse,
    /// The emergency stop of the layout (B-23).
    TogglePower,
    /// Stops only the loco of the device (B-23).
    EmergencyStop,
    /// Switches the device to the previous free loco in the list (B-23).
    PreviousLoco,
    NextLoco,
    /// A logical action (N-07).
    Action {
        action: u32,
    },
}

fn default_dead_zone() -> f64 {
    DEAD_ZONE
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Binding {
    pub control: String,
    pub target: Target,
}

/// The bindings of all devices of one `kind`.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Mapping {
    pub kind: String,
    pub bindings: Vec<Binding>,
}

impl Mapping {
    /// The standard mapping for unknown devices, after Electrip 1: left
    /// stick drives, A is the emergency stop, B the direction switch and
    /// the d-pad changes the loco.
    pub fn new(kind: String) -> Self {
        let bindings = [
            (
                "lefty",
                Target::Drive {
                    dead_zone: default_dead_zone(),
                },
            ),
            ("a", Target::TogglePower),
            ("b", Target::Reverse),
            ("dpleft", Target::PreviousLoco),
            ("dpright", Target::NextLoco),
        ];
        Mapping {
            kind,
            bindings: bindings
                .into_iter()
                .map(|(control, target)| Binding {
                    control: control.into(),
                    target,
                })
                .collect(),
        }
    }

    pub fn target(&self, control: &str) -> Option<&Target> {
        let binding = self.bindings.iter().find(|b| b.control == control);
        binding.map(|b| &b.target)
    }

    /// Maps the control to `target` instead of what it did before.
    pub fn bind(&mut self, control: String, target: Target) {
        self.unbind(&control);
        self.bindings.push(Binding { control, target });
    }

    pub fn unbind(&mut self, control: &str) {
        self.bindings.retain(|b| b.control != control);
    }
}

/// A connected input device and the loco it controls.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Device {
    pub id: u32,
    pub kind: String,
    pub loco: Option<u32>,
    /// The buttons held down now.
    #[serde(skip)]
    held: Vec<String>,
}

impl Device {
    pub fn new(id: u32, kind: String) -> Self {
        Device {
            id,
            kind,
            loco: None,
            held: Vec::new(),
        }
    }

    /// Records whether the button is held; returns whether that changed.
    pub fn press(&mut self, control: &str, pressed: bool) -> bool {
        let held = self.held.iter().position(|c| c == control);
        match (held, pressed) {
            (None, true) => self.held.push(control.into()),
            (Some(index), false) => {
                self.held.remove(index);
            }
            _ => return false,
        }
        true
    }
}

#[cfg(test)]
mod tests;
