use super::*;
use Protocol::*;

#[test]
fn ranges_match_the_requirement() {
    let expected: [(Protocol, u16, &[u8]); 4] = [
        (Motorola1, 80, &[14]),
        (Motorola2, 255, &[14, 28]),
        (DccShort, 127, &[14, 28, 128]),
        (DccLong, 10239, &[14, 28, 128]),
    ];
    for (protocol, max_address, steps) in expected {
        assert_eq!(protocol.max_address(), max_address, "{protocol:?}");
        assert_eq!(protocol.speed_step_options(), steps, "{protocol:?}");
    }
}

#[test]
fn new_accepts_valid_combinations() {
    let decoder = Decoder::new(DccLong, 10239, 28).unwrap();
    assert_eq!(
        (decoder.protocol(), decoder.address(), decoder.speed_steps()),
        (DccLong, 10239, 28)
    );
    assert!(Decoder::new(Motorola1, 1, 14).is_ok());
}

#[test]
fn new_rejects_invalid_address() {
    assert_eq!(
        Decoder::new(DccShort, 128, 128),
        Err(DecoderError::AddressOutOfRange { max: 127 })
    );
    assert_eq!(
        Decoder::new(Motorola1, 0, 14),
        Err(DecoderError::AddressOutOfRange { max: 80 })
    );
}

#[test]
fn new_rejects_unsupported_speed_steps() {
    assert_eq!(
        Decoder::new(Motorola2, 3, 128),
        Err(DecoderError::SpeedStepsNotSupported { options: &[14, 28] })
    );
}

#[test]
fn rejected_change_keeps_the_decoder_unchanged() {
    let mut decoder = Decoder::new(Motorola2, 200, 28).unwrap();
    let before = decoder;
    assert!(decoder.set_address(256).is_err());
    assert!(decoder.set_speed_steps(128).is_err());
    assert_eq!(decoder, before);
}

#[test]
fn protocol_switch_caps_address_and_sets_highest_speed_steps() {
    let mut decoder = Decoder::new(DccLong, 3000, 14).unwrap();
    decoder.set_protocol(Motorola2);
    assert_eq!((decoder.address(), decoder.speed_steps()), (255, 28));
    decoder.set_protocol(DccShort);
    assert_eq!((decoder.address(), decoder.speed_steps()), (127, 128));
    decoder.set_protocol(Motorola1);
    assert_eq!((decoder.address(), decoder.speed_steps()), (80, 14));
}

#[test]
fn protocol_switch_keeps_address_in_range() {
    let mut decoder = Decoder::new(Motorola1, 42, 14).unwrap();
    decoder.set_protocol(DccLong);
    assert_eq!((decoder.address(), decoder.speed_steps()), (42, 128));
}
