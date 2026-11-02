//! The commands for logical actions (N-07) and the functions of a loco
//! mapped to them (B-07).

use super::{CommandError, Session, check_index};
use crate::function::{Action, Function};
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
        let functions = std::mem::take(loco.functions_mut());
        for function in functions {
            if let Some(action) = actions.iter().find(|a| a.id == function.action) {
                let action = self.action_named(&action.name);
                let on = function.default_on;
                loco.functions_mut().push(Function {
                    action,
                    on,
                    ..function
                });
            }
        }
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

    pub(super) fn remove_function(&mut self, loco: u32, index: usize) -> Result<(), CommandError> {
        let functions = self.loco(loco)?.functions_mut();
        check_index(functions, index)?;
        functions.remove(index);
        Ok(())
    }

    pub(super) fn move_function(
        &mut self,
        loco: u32,
        index: usize,
        position: usize,
    ) -> Result<(), CommandError> {
        let functions = self.loco(loco)?.functions_mut();
        check_index(functions, index)?;
        check_index(functions, position)?;
        let function = functions.remove(index);
        functions.insert(position, function);
        Ok(())
    }

    /// An action without a function at this loco does nothing.
    pub(super) fn trigger_action(
        &mut self,
        loco: u32,
        action: u32,
        pressed: bool,
    ) -> Result<(), CommandError> {
        self.action(action)?;
        let functions = self.loco(loco)?.functions_mut();
        for function in functions.iter_mut().filter(|f| f.action == action) {
            function.trigger(pressed);
        }
        Ok(())
    }
}
