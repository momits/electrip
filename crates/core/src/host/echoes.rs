//! What the host sent recently. The command station reports each change
//! back to all its clients; until the report arrives it is an echo, not a
//! change by another program (ADR 0010).

use crate::station::{LocoState, MAX_FUNCTION};

/// How long the command station may take to report back what the host
/// sent.
const SECONDS: f64 = 1.0;

#[derive(Default)]
pub(super) struct Echoes {
    /// The seconds the host has polled.
    clock: f64,
    /// The time, address and state of each loco state sent recently.
    sent: Vec<(f64, u16, LocoState)>,
}

impl Echoes {
    pub(super) fn tick(&mut self, seconds: f64) {
        self.clock += seconds;
        let now = self.clock;
        self.sent.retain(|sent| now - sent.0 < SECONDS);
    }

    /// Notes a state sent to `address` and the state before it, since the
    /// command station may report a mix of both while it switches.
    pub(super) fn note(&mut self, address: u16, before: Option<LocoState>, state: LocoState) {
        for state in before.into_iter().chain([state]) {
            self.sent.push((self.clock, address, state));
        }
    }

    /// Whether the host sent the drive and each function of `state`
    /// recently. A Z21 switches each function on its own and reports the
    /// loco after each.
    pub(super) fn contains(&self, address: u16, state: &LocoState) -> bool {
        let sent: Vec<&LocoState> = self
            .sent
            .iter()
            .filter(|s| s.1 == address)
            .map(|s| &s.2)
            .collect();
        sent.iter()
            .any(|s| (s.forward, s.step) == (state.forward, state.step))
            && (0..=MAX_FUNCTION).all(|n| sent.iter().any(|s| s.function(n) == state.function(n)))
    }
}

#[cfg(test)]
mod tests;
