//! The commands for input devices and their mappings (N-01, B-02).

use super::{Command, CommandError, LocoEntry, Session};
use crate::input::{Device, Mapping, Target};
use std::mem;

impl Session {
    pub fn devices(&self) -> &[Device] {
        &self.devices
    }

    pub fn mappings(&self) -> &[Mapping] {
        &self.mappings
    }

    pub(super) fn add_device(&mut self, id: u32, kind: String) -> Result<(), CommandError> {
        if self.devices.iter().any(|d| d.id == id) {
            return Err(CommandError::DeviceExists(id));
        }
        self.mapping(kind.clone());
        self.devices.push(Device::new(id, kind));
        Ok(())
    }

    /// Releases the axis of the loco, so it keeps its speed.
    pub(super) fn remove_device(&mut self, id: u32) -> Result<(), CommandError> {
        let device = self.devices.remove(self.device_index(id)?);
        if let Some(entry) = device.loco.and_then(|loco| self.entry(loco).ok()) {
            entry.axis.deflection = 0.0;
        }
        Ok(())
    }

    pub(super) fn bind(
        &mut self,
        kind: String,
        control: String,
        target: Target,
    ) -> Result<(), CommandError> {
        if let Target::Action { action } = target {
            self.action(action)?;
        }
        self.mapping(kind).bind(control, target);
        Ok(())
    }

    /// The mapping of the device type; an unknown type gets the standard
    /// mapping.
    pub(super) fn mapping(&mut self, kind: String) -> &mut Mapping {
        let index = match self.mappings.iter().position(|m| m.kind == kind) {
            Some(index) => index,
            None => {
                self.mappings.push(Mapping::new(kind));
                self.mappings.len() - 1
            }
        };
        &mut self.mappings[index]
    }

    /// Handles a control of a device through its mapping. Returns the
    /// command the host executes; drive axes and loco changes are handled
    /// here. A control without a target, or one that needs a loco while
    /// the device has none, does nothing.
    pub(crate) fn input(
        &mut self,
        id: u32,
        control: &str,
        value: f64,
    ) -> Result<Option<Command>, CommandError> {
        let index = self.device_index(id)?;
        let device = &self.devices[index];
        let mapping = self.mappings.iter().find(|m| m.kind == device.kind);
        let Some(target) = mapping.and_then(|m| m.target(control)).cloned() else {
            return Ok(None);
        };
        let loco = device.loco;
        if let Target::Drive { dead_zone } = target {
            if let Some(loco) = loco {
                self.set_axis(loco, -value, dead_zone)?;
            }
            return Ok(None);
        }
        let pressed = value >= 0.5;
        if !self.devices[index].press(control, pressed) {
            return Ok(None);
        }
        Ok(match (&target, loco) {
            (&Target::Action { action }, Some(loco)) => Some(Command::TriggerAction {
                loco,
                action,
                pressed,
            }),
            _ if !pressed => None,
            (Target::TogglePower, _) => Some(Command::TogglePower),
            (Target::Reverse, Some(loco)) => Some(Command::Reverse { loco }),
            (Target::EmergencyStop, Some(loco)) => Some(Command::EmergencyStop { loco }),
            (Target::PreviousLoco | Target::NextLoco, _) => {
                self.change_loco(index, target == Target::NextLoco);
                None
            }
            _ => None,
        })
    }

    /// Switches the device to the next loco in the list (or the previous
    /// one) that no other device controls, like Electrip 1. The axis of
    /// the device moves along.
    fn change_loco(&mut self, device: usize, forward: bool) -> Option<()> {
        let current = self.devices[device].loco?;
        let position = self.index(current).ok()?;
        let taken: Vec<u32> = self.devices.iter().filter_map(|d| d.loco).collect();
        let free = |e: &&LocoEntry| !taken.contains(&e.id);
        let next = if forward {
            self.locos[position + 1..].iter().find(free)
        } else {
            self.locos[..position].iter().rev().find(free)
        }?
        .id;
        let axis = mem::take(&mut self.locos[position].axis);
        self.entry(next).ok()?.axis = axis;
        self.devices[device].loco = Some(next);
        Some(())
    }

    /// Gives each device without a loco, or whose loco was removed, the
    /// first loco no other device controls.
    pub(super) fn assign_locos(&mut self) {
        for index in 0..self.devices.len() {
            let loco = self.devices[index].loco;
            if loco.is_some_and(|id| self.index(id).is_ok()) {
                continue;
            }
            let taken: Vec<u32> = self.devices.iter().filter_map(|d| d.loco).collect();
            let free = self.locos.iter().find(|e| !taken.contains(&e.id));
            self.devices[index].loco = free.map(|e| e.id);
        }
    }

    fn device_index(&self, id: u32) -> Result<usize, CommandError> {
        self.devices
            .iter()
            .position(|d| d.id == id)
            .ok_or(CommandError::UnknownDevice(id))
    }
}
