use super::*;

fn loco(forward: bool, step: u8, functions: u32) -> LocoState {
    LocoState {
        forward,
        step,
        functions,
    }
}

#[test]
fn a_mix_of_the_sent_states_is_an_echo() {
    let mut echoes = Echoes::default();
    echoes.note(3, Some(loco(true, 10, 0b00)), loco(true, 11, 0b11));
    assert!(echoes.contains(3, &loco(true, 11, 0b01)));
    assert!(echoes.contains(3, &loco(true, 10, 0b11)));
    assert!(!echoes.contains(3, &loco(false, 11, 0b11)));
    assert!(!echoes.contains(3, &loco(true, 11, 0b111)));
    assert!(!echoes.contains(4, &loco(true, 11, 0b11)));
}

#[test]
fn an_echo_ends_after_a_second() {
    let mut echoes = Echoes::default();
    echoes.note(3, None, loco(true, 10, 0));
    echoes.tick(0.9);
    assert!(echoes.contains(3, &loco(true, 10, 0)));
    echoes.tick(0.1);
    assert!(!echoes.contains(3, &loco(true, 10, 0)));
}
