use super::*;

fn function(mode: Mode, default_on: bool) -> Function {
    Function {
        action: 1,
        number: 0,
        name: String::new(),
        mode,
        default_on,
        on: default_on,
    }
}

/// Whether the function is on after each step of pressing (`true`) and
/// releasing (`false`) the action.
fn states(mut function: Function, steps: &[bool]) -> Vec<bool> {
    steps
        .iter()
        .map(|&pressed| {
            function.trigger(pressed);
            function.on
        })
        .collect()
}

const PRESS_RELEASE_TWICE: [bool; 4] = [true, false, true, false];

#[test]
fn a_switch_toggles_on_each_press() {
    let states = states(function(Mode::Switch, false), &PRESS_RELEASE_TWICE);
    assert_eq!(states, [true, true, false, false]);
}

#[test]
fn a_push_button_is_on_while_held() {
    let states = states(function(Mode::Push, false), &PRESS_RELEASE_TWICE);
    assert_eq!(states, [true, false, true, false]);
}

#[test]
fn default_on_inverts_a_switch() {
    let states = states(function(Mode::Switch, true), &PRESS_RELEASE_TWICE);
    assert_eq!(states, [false, false, true, true]);
}

#[test]
fn default_on_inverts_a_push_button() {
    let states = states(function(Mode::Push, true), &PRESS_RELEASE_TWICE);
    assert_eq!(states, [false, true, false, true]);
}
