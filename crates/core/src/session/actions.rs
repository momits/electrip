//! The commands for logical actions (N-07) and the functions and sound
//! functions of a loco mapped to them (B-07, B-16).

use super::{CommandError, Session};
use crate::audio::AudioSink;
use crate::function::{Action, Function};
use crate::function_sound::{self, SoundFunction};
use crate::input::Target;
use crate::loco::Loco;
use crate::station::MAX_FUNCTION;

impl Session {
    pub fn actions(&self) -> &[Action] {
        &self.actions
    }

    pub(super) fn add_action(&mut self, name: String) {
        self.last_action_id += 1;
        self.actions.push(Action {
            id: self.last_action_id,
            name,
        });
    }

    /// Appends a loco of a package (B-20); its functions get the actions of
    /// this configuration with the names of their `actions`, which are added
    /// if missing. Functions with an unknown action are left out.
    pub(crate) fn import_loco(&mut self, mut loco: Loco, actions: &[Action], report: Vec<String>) {
        let mut action = |old: u32| {
            let name = &actions.iter().find(|a| a.id == old)?.name;
            Some(self.action_named(name))
        };
        let functions = std::mem::take(loco.functions_mut());
        *loco.functions_mut() = functions
            .into_iter()
            .filter_map(|f| {
                let (action, on) = (action(f.action)?, f.default_on);
                Some(Function { action, on, ..f })
            })
            .collect();
        let sounds = std::mem::take(loco.sound_functions_mut());
        *loco.sound_functions_mut() = sounds
            .into_iter()
            .filter_map(|f| {
                let mut function = f.off();
                function.action = action(f.action)?;
                Some(function)
            })
            .collect();
        self.push(loco);
        self.import_report = report;
    }

    /// The id of the action `name`; adds it if missing.
    fn action_named(&mut self, name: &str) -> u32 {
        match self.actions.iter().find(|a| a.name == name) {
            Some(action) => action.id,
            None => {
                self.add_action(name.into());
                self.last_action_id
            }
        }
    }

    pub(super) fn remove_action(&mut self, id: u32) -> Result<(), CommandError> {
        let index = self.actions.iter().position(|a| a.id == id);
        self.actions
            .remove(index.ok_or(CommandError::UnknownAction(id))?);
        for entry in &mut self.locos {
            entry.loco.functions_mut().retain(|f| f.action != id);
            entry.loco.sound_functions_mut().retain(|f| f.action != id);
        }
        let target = Target::Action { action: id };
        for mapping in &mut self.mappings {
            mapping.bindings.retain(|b| b.target != target);
        }
        Ok(())
    }

    pub(super) fn action(&mut self, id: u32) -> Result<&mut Action, CommandError> {
        self.actions
            .iter_mut()
            .find(|a| a.id == id)
            .ok_or(CommandError::UnknownAction(id))
    }

    /// Appends the function, switched to its default state.
    pub(super) fn add_function(
        &mut self,
        loco: u32,
        function: Function,
    ) -> Result<(), CommandError> {
        self.action(function.action)?;
        if function.number > MAX_FUNCTION {
            return Err(CommandError::FunctionOutOfRange(function.number));
        }
        let on = function.default_on;
        self.loco(loco)?
            .functions_mut()
            .push(Function { on, ..function });
        Ok(())
    }

    /// Appends the sound function, switched off.
    pub(super) fn add_sound_function(
        &mut self,
        loco: u32,
        function: SoundFunction,
    ) -> Result<(), CommandError> {
        self.action(function.action)?;
        let function = function.off();
        self.loco(loco)?.sound_functions_mut().push(function);
        Ok(())
    }

    /// An action without a function at this loco does nothing.
    pub(crate) fn trigger_action(
        &mut self,
        loco: u32,
        action: u32,
        pressed: bool,
        sink: &mut dyn AudioSink,
    ) -> Result<(), CommandError> {
        self.action(action)?;
        let loco_entry = self.loco(loco)?;
        let functions = loco_entry.functions_mut();
        for function in functions.iter_mut().filter(|f| f.action == action) {
            function.trigger(pressed);
        }
        let sounds = loco_entry.sound_functions_mut();
        function_sound::trigger(sounds, loco, action, pressed, sink);
        Ok(())
    }
}
