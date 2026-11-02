use super::*;

#[test]
fn switches_single_functions() {
    let mut state = LocoState::default();
    state.set_function(0, true);
    state.set_function(MAX_FUNCTION, true);
    state.set_function(0, false);
    assert!(!state.function(0));
    assert!(state.function(MAX_FUNCTION));
    assert_eq!(state.functions, 1 << 28);
}
