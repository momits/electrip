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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Binding {
    pub control: String,
    pub target: Target,
}

/// The bindings of all devices of one `kind`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
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
    #[serde(skip)]
    scroll: Option<Scroll>,
}

/// Holding "previous/next loco" changes the loco again after 500 ms and
/// then every 60 ms, like Electrip 1 (B-23).
const SCROLL_DELAY: f64 = 0.5;
const SCROLL_INTERVAL: f64 = 0.06;

/// A held loco change.
#[derive(Debug, Clone, PartialEq)]
struct Scroll {
    control: String,
    forward: bool,
    seconds: f64,
}

impl Scroll {
    /// The loco changes after the first one, up to `seconds` of holding.
    fn steps(seconds: f64) -> u32 {
        ((seconds - SCROLL_DELAY) / SCROLL_INTERVAL).max(0.0) as u32
    }
}

impl Device {
    pub fn new(id: u32, kind: String) -> Self {
        Device {
            id,
            kind,
            loco: None,
            held: Vec::new(),
            scroll: None,
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

    /// Starts scrolling while `control` is held.
    pub fn start_scroll(&mut self, control: &str, forward: bool) {
        self.scroll = Some(Scroll {
            control: control.into(),
            forward,
            seconds: 0.0,
        });
    }

    /// Stops scrolling if `control` started it.
    pub fn release(&mut self, control: &str) {
        if self.scroll.as_ref().is_some_and(|s| s.control == control) {
            self.scroll = None;
        }
    }

    /// Holds the scroll for `seconds` longer; returns the direction and
    /// how many times the loco changes now.
    pub fn scroll(&mut self, seconds: f64) -> Option<(bool, u32)> {
        let scroll = self.scroll.as_mut()?;
        let before = Scroll::steps(scroll.seconds);
        scroll.seconds += seconds;
        Some((scroll.forward, Scroll::steps(scroll.seconds) - before))
    }
}

#[cfg(test)]
mod tests;
