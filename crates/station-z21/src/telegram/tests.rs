use super::*;

fn dcc(address: u16, steps: u8) -> Decoder {
    Decoder::new(Protocol::DccLong, address, steps).unwrap()
}

/// The data of a dataset after length and header.
fn data(dataset: &[u8]) -> &[u8] {
    &dataset[4..]
}

#[test]
fn frames_x_bus_commands_with_length_header_and_checksum() {
    assert_eq!(get_status(), [0x07, 0x00, 0x40, 0x00, 0x21, 0x24, 0x05]);
    assert_eq!(set_power(false), [0x07, 0x00, 0x40, 0x00, 0x21, 0x80, 0xA1]);
    assert_eq!(set_power(true), [0x07, 0x00, 0x40, 0x00, 0x21, 0x81, 0xA0]);
    assert_eq!(logoff(), [0x04, 0x00, 0x30, 0x00]);
    assert_eq!(
        set_broadcast_flags(),
        [0x08, 0x00, 0x50, 0x00, 0x01, 0x00, 0x01, 0x00]
    );
}

#[test]
fn encodes_speed_steps_in_each_format() {
    let drive = |steps, step| data(&set_loco_drive(&dcc(3, steps), true, step, false))[4];
    assert_eq!(drive(14, 0), 0x80);
    assert_eq!(drive(14, 14), 0x80 | 15);
    assert_eq!(drive(28, 1), 0x80 | 0x02);
    assert_eq!(drive(28, 2), 0x80 | 0x12);
    assert_eq!(drive(28, 28), 0x80 | 0x1F);
    assert_eq!(drive(128, 1), 0x80 | 2);
    assert_eq!(drive(128, 126), 0x80 | 127);
    let stop = set_loco_drive(&dcc(3, 28), false, 9, true);
    assert_eq!(data(&stop)[..5], [0xE4, 0x12, 0x00, 0x03, 0x01]);
}

#[test]
fn marks_addresses_from_128_on() {
    assert_eq!(
        data(&set_loco_function(127, 0, true))[..5],
        [0xE4, 0xF8, 0x00, 0x7F, 0x40]
    );
    assert_eq!(
        data(&set_loco_function(1000, 28, false))[..5],
        [0xE4, 0xF8, 0xC3, 0xE8, 28]
    );
    let motorola = Decoder::new(Protocol::Motorola2, 200, 28).unwrap();
    assert_eq!(
        set_loco_mode(&motorola),
        [0x07, 0x00, 0x61, 0x00, 0x00, 200, 0x01]
    );
    assert_eq!(set_loco_mode(&dcc(1000, 128))[4..], [0x03, 0xE8, 0x00]);
    assert_eq!(
        get_loco_info(3),
        [0x09, 0x00, 0x40, 0x00, 0xE3, 0xF0, 0x00, 0x03, 0x10]
    );
    assert_eq!(data(&get_loco_info(1000))[..4], [0xE3, 0xF0, 0xC3, 0xE8]);
}

/// LAN_X_LOCO_INFO with checksum.
fn loco_info(bytes: [u8; 8]) -> Vec<u8> {
    x_bus(&[&[0xEF], &bytes[..]].concat())
}

#[test]
fn reads_what_it_sends() {
    for (steps, format) in [(14, 0), (28, 2), (128, 4)] {
        for step in [0, 1, 2, 13, 14] {
            let drive = set_loco_drive(&dcc(1000, steps), false, step, false);
            let (address, speed) = (&data(&drive)[2..4], data(&drive)[4]);
            let info = loco_info([address[0], address[1], format, speed, 0, 0, 0, 0]);
            let state = LocoState {
                forward: false,
                step,
                functions: 0,
            };
            assert_eq!(
                parse(&info),
                [StationEvent::Loco {
                    address: 1000,
                    state
                }]
            );
        }
    }
}

#[test]
fn reads_functions_and_direction_of_a_loco() {
    let info = loco_info([0x00, 0x05, 0x04, 0x80 | 11, 0b1_0010, 0x81, 0x01, 0x80]);
    let state = LocoState {
        forward: true,
        step: 10,
        functions: 1 | 1 << 2 | 1 << 5 | 1 << 12 | 1 << 13 | 1 << 28,
    };
    assert_eq!(parse(&info), [StationEvent::Loco { address: 5, state }]);
}

#[test]
fn reads_power_from_status_and_broadcasts() {
    let packet = [
        x_bus(&[0x61, 0x01]),
        x_bus(&[0x61, 0x00]),
        x_bus(&[0x81, 0x00]),
        x_bus(&[0x62, 0x22, 0x00]),
        x_bus(&[0x62, 0x22, 0x02]),
    ]
    .concat();
    let power = |on| StationEvent::Power(on);
    assert_eq!(
        parse(&packet),
        [
            power(true),
            power(false),
            power(false),
            power(true),
            power(false)
        ]
    );
}

#[test]
fn ignores_bad_checksums_other_headers_and_truncated_datasets() {
    assert_eq!(parse(&[0x07, 0x00, 0x40, 0x00, 0x61, 0x01, 0x00]), []);
    assert_eq!(parse(&[0x08, 0x00, 0x10, 0x00, 1, 2, 3, 4]), []);
    let mut packet = x_bus(&[0x61, 0x01]);
    packet.extend([0x09, 0x00, 0x40]);
    assert_eq!(parse(&packet), [StationEvent::Power(true)]);
}

#[test]
fn tells_motorola_from_dcc_by_the_format_and_scales_the_steps() {
    let drive = |decoder: &Decoder, step| {
        let dataset = set_loco_drive(decoder, true, step, false);
        (data(&dataset)[1], data(&dataset)[4] & 0x7F)
    };
    let mm1 = Decoder::new(Protocol::Motorola1, 5, 14).unwrap();
    let mm2_14 = Decoder::new(Protocol::Motorola2, 5, 14).unwrap();
    let mm2_28 = Decoder::new(Protocol::Motorola2, 5, 28).unwrap();
    assert_eq!(drive(&mm1, 14), (0x10, 15));
    assert_eq!(drive(&mm2_14, 14), (0x12, 0x1F));
    assert_eq!(drive(&mm2_28, 28), (0x13, 127));
}

#[test]
fn reads_back_the_steps_it_scaled() {
    for (protocol, steps) in [
        (Protocol::Motorola1, 14),
        (Protocol::Motorola2, 14),
        (Protocol::Motorola2, 28),
        (Protocol::DccLong, 28),
    ] {
        let decoder = Decoder::new(protocol, 5, steps).unwrap();
        for step in 0..=steps {
            let sent = scale(step, steps, drive_format(&decoder).1);
            assert_eq!(host_step(&decoder, sent), step, "{protocol:?} {steps}");
        }
    }
}
