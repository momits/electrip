use super::*;

/// The simulator on a virtual clock; clients are told apart by port.
struct Sim {
    z21: Z21,
    now: Instant,
}

impl Sim {
    fn new() -> Self {
        Sim {
            z21: Z21::default(),
            now: Instant::now(),
        }
    }

    fn send(&mut self, client: u16, packet: &[u8]) -> Vec<Packet> {
        self.z21.handle(addr(client), packet, self.now)
    }

    /// Sends a packet and returns only the replies to the sender.
    fn ask(&mut self, client: u16, packet: &[u8]) -> Vec<Vec<u8>> {
        received(&self.send(client, packet), client)
    }

    fn set_flags(&mut self, client: u16, flags: u32) {
        self.send(client, &dataset(0x50, &flags.to_le_bytes()));
    }
}

fn addr(port: u16) -> SocketAddr {
    SocketAddr::from(([127, 0, 0, 1], port))
}

fn received(packets: &[Packet], client: u16) -> Vec<Vec<u8>> {
    packets
        .iter()
        .filter(|(to, _)| *to == addr(client))
        .map(|(_, bytes)| bytes.clone())
        .collect()
}

/// LAN_X request for loco 3 or another short address.
fn loco_request(x_header: u8, db0: u8, address: u8, value: u8) -> Vec<u8> {
    x_dataset(&[x_header, db0, 0x00, address, value])
}

// Conformance: request and reply telegrams as printed in the specification.

#[test]
fn serial_number() {
    let mut sim = Sim::new();
    let reply = sim.ask(1, &[0x04, 0x00, 0x10, 0x00]);
    let serial = SERIAL_NUMBER.to_le_bytes();
    assert_eq!(reply, [[&[0x08, 0x00, 0x10, 0x00][..], &serial].concat()]);
}

#[test]
fn x_bus_version() {
    let mut sim = Sim::new();
    let reply = sim.ask(1, &[0x07, 0x00, 0x40, 0x00, 0x21, 0x21, 0x00]);
    assert_eq!(
        reply,
        [[0x09, 0x00, 0x40, 0x00, 0x63, 0x21, 0x30, 0x12, 0x60]]
    );
}

#[test]
fn status_track_power_and_stop() {
    let mut sim = Sim::new();
    let status = [0x07, 0x00, 0x40, 0x00, 0x21, 0x24, 0x05];
    assert_eq!(
        sim.ask(1, &status),
        [[0x08, 0x00, 0x40, 0x00, 0x62, 0x22, 0x00, 0x40]]
    );

    let off = sim.ask(1, &[0x07, 0x00, 0x40, 0x00, 0x21, 0x80, 0xa1]);
    assert_eq!(off, [[0x07, 0x00, 0x40, 0x00, 0x61, 0x00, 0x61]]);
    assert_eq!(
        sim.ask(1, &status),
        [[0x08, 0x00, 0x40, 0x00, 0x62, 0x22, 0x02, 0x42]]
    );

    let on = sim.ask(1, &[0x07, 0x00, 0x40, 0x00, 0x21, 0x81, 0xa0]);
    assert_eq!(on, [[0x07, 0x00, 0x40, 0x00, 0x61, 0x01, 0x60]]);

    let stop = sim.ask(1, &[0x06, 0x00, 0x40, 0x00, 0x80, 0x80]);
    assert_eq!(stop, [[0x07, 0x00, 0x40, 0x00, 0x81, 0x00, 0x81]]);
    assert_eq!(
        sim.ask(1, &status),
        [[0x08, 0x00, 0x40, 0x00, 0x62, 0x22, 0x01, 0x41]]
    );

    // Track power on ends the emergency stop (spec 2.6).
    sim.ask(1, &[0x07, 0x00, 0x40, 0x00, 0x21, 0x81, 0xa0]);
    assert_eq!(
        sim.ask(1, &status),
        [[0x08, 0x00, 0x40, 0x00, 0x62, 0x22, 0x00, 0x40]]
    );
}

#[test]
fn firmware_version() {
    // Example of spec 2.15: "Firmware Version 1.23".
    let example = [0x09, 0x00, 0x40, 0x00, 0xf3, 0x0a, 0x01, 0x23, 0xdb];
    assert_eq!(x_dataset(&[0xf3, 0x0a, 0x01, 0x23]), example);

    let mut sim = Sim::new();
    let reply = sim.ask(1, &[0x07, 0x00, 0x40, 0x00, 0xF1, 0x0A, 0xFB]);
    assert_eq!(
        reply,
        [[0x09, 0x00, 0x40, 0x00, 0xf3, 0x0a, 0x01, 0x43, 0xbb]]
    );
}

#[test]
fn hardware_info() {
    // Same layout as the example of spec 2.20, with type 0x201 and V1.43.
    let mut sim = Sim::new();
    let reply = sim.ask(1, &[0x04, 0x00, 0x1A, 0x00]);
    let expected = [
        0x0C, 0x00, 0x1A, 0x00, 0x01, 0x02, 0x00, 0x00, 0x43, 0x01, 0x00, 0x00,
    ];
    assert_eq!(reply, [expected]);
}

#[test]
fn unknown_command() {
    let mut sim = Sim::new();
    let unknown = [0x07, 0x00, 0x40, 0x00, 0x61, 0x82, 0xE3];
    // Wrong XOR byte.
    assert_eq!(
        sim.ask(1, &[0x07, 0x00, 0x40, 0x00, 0x21, 0x24, 0x00]),
        [unknown]
    );
    // Unknown X-Header.
    assert_eq!(sim.ask(1, &x_dataset(&[0x77])), [unknown]);
    // Unknown speed step format and function index above F31.
    assert_eq!(sim.ask(1, &loco_request(0xE4, 0x11, 3, 0x00)), [unknown]);
    assert_eq!(sim.ask(1, &loco_request(0xE4, 0xF8, 3, 0x60)), [unknown]);
    // Switch type 11 is not allowed.
    assert_eq!(sim.ask(1, &loco_request(0xE4, 0xF8, 3, 0xC0)), [unknown]);
}

#[test]
fn broadcast_flags() {
    let mut sim = Sim::new();
    assert!(
        sim.ask(1, &[0x08, 0x00, 0x50, 0x00, 0x01, 0x01, 0x00, 0x00])
            .is_empty()
    );
    let reply = sim.ask(1, &[0x04, 0x00, 0x51, 0x00]);
    assert_eq!(reply, [[0x08, 0x00, 0x51, 0x00, 0x01, 0x01, 0x00, 0x00]]);
    // Flags belong to one client (IP and port).
    assert_eq!(
        sim.ask(2, &[0x04, 0x00, 0x51, 0x00]),
        [[0x08, 0x00, 0x51, 0x00, 0, 0, 0, 0]]
    );
}

#[test]
fn combined_data_sets() {
    let mut sim = Sim::new();
    let packet = [
        [0x04, 0x00, 0x51, 0x00].as_slice(),
        &[0x07, 0x00, 0x40, 0x00, 0x21, 0x21, 0x00],
    ]
    .concat();
    let replies = sim.ask(1, &packet);
    assert_eq!(replies.len(), 2);
    assert_eq!(replies[0], [0x08, 0x00, 0x51, 0x00, 0, 0, 0, 0]);
    assert_eq!(replies[1][4..6], [0x63, 0x21]);
    // A truncated data set at the end is dropped.
    assert_eq!(
        sim.ask(1, &[0x04, 0x00, 0x51, 0x00, 0x08, 0x00, 0x10])
            .len(),
        1
    );
}

#[test]
fn loco_mode() {
    let mut sim = Sim::new();
    assert!(
        sim.ask(1, &[0x07, 0x00, 0x61, 0x00, 0x00, 0x03, 0x01])
            .is_empty()
    );
    assert_eq!(
        sim.ask(1, &[0x06, 0x00, 0x60, 0x00, 0x00, 0x03]),
        [[0x07, 0x00, 0x60, 0x00, 0x00, 0x03, 0x01]]
    );
    // Addresses from 256 on stay DCC.
    sim.ask(1, &[0x07, 0x00, 0x61, 0x00, 0x01, 0x2C, 0x01]);
    assert_eq!(
        sim.ask(1, &[0x06, 0x00, 0x60, 0x00, 0x01, 0x2C]),
        [[0x07, 0x00, 0x60, 0x00, 0x01, 0x2C, 0x00]]
    );
}

#[test]
fn system_state() {
    let mut sim = Sim::new();
    sim.ask(1, &[0x07, 0x00, 0x40, 0x00, 0x21, 0x80, 0xa1]);
    let reply = sim.ask(1, &[0x04, 0x00, 0x85, 0x00]);
    assert_eq!(reply.len(), 1);
    assert_eq!(reply[0][..4], [0x14, 0x00, 0x84, 0x00]);
    assert_eq!(reply[0][4 + 12], CS_TRACK_VOLTAGE_OFF);
    assert_eq!(reply[0][4 + 15], CAPABILITIES);
}

// Driving (spec chapter 4).

#[test]
fn loco_info_of_new_loco() {
    let mut sim = Sim::new();
    let reply = sim.ask(1, &[0x09, 0x00, 0x40, 0x00, 0xE3, 0xF0, 0x00, 0x03, 0x10]);
    let info = [
        0x0F, 0x00, 0x40, 0x00, 0xEF, 0x00, 0x03, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xE8,
    ];
    assert_eq!(reply, [info]);
}

#[test]
fn drive_reaches_subscribed_clients_only() {
    let mut sim = Sim::new();
    // Client 1 subscribes loco 3, client 2 sets the flag only, client 3
    // subscribes without the flag, client 4 wants all locos.
    sim.set_flags(1, BC_DRIVE_SWITCH);
    sim.ask(1, &x_dataset(&[0xE3, 0xF0, 0x00, 0x03]));
    sim.set_flags(2, BC_DRIVE_SWITCH);
    sim.ask(3, &x_dataset(&[0xE3, 0xF0, 0x00, 0x03]));
    sim.set_flags(4, BC_DRIVE_SWITCH | BC_ALL_LOCOS);

    // Client 5 drives loco 3 forward at step 19 of 128.
    let sent = sim.send(
        5,
        &[0x0A, 0x00, 0x40, 0x00, 0xE4, 0x13, 0x00, 0x03, 0x94, 0x60],
    );
    let info = [
        0x0F, 0x00, 0x40, 0x00, 0xEF, 0x00, 0x03, 0x04, 0x94, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7C,
    ];
    assert_eq!(received(&sent, 1), [info]);
    assert_eq!(received(&sent, 4), [info]);
    assert_eq!(sent.len(), 2);
}

#[test]
fn speed_step_formats() {
    let mut sim = Sim::new();
    sim.set_flags(1, BC_DRIVE_SWITCH | BC_ALL_LOCOS);
    for (format, steps) in [(0x10, 0), (0x12, 2), (0x13, 4)] {
        let reply = sim.ask(1, &loco_request(0xE4, format, 3, 0x85));
        assert_eq!(reply[0][7..9], [steps, 0x85]);
    }
}

#[test]
fn functions_f0_to_f31() {
    let mut sim = Sim::new();
    sim.set_flags(1, BC_DRIVE_SWITCH | BC_ALL_LOCOS);
    // F0 on, F1 on, F12 on, F13 on, F28 on, F31 toggled on, F1 off again.
    for code in [0x40, 0x41, 0x4C, 0x4D, 0x5C, 0x9F, 0x01] {
        sim.ask(1, &loco_request(0xE4, 0xF8, 3, code));
    }
    let reply = sim.ask(1, &x_dataset(&[0xE3, 0xF0, 0x00, 0x03]));
    assert_eq!(reply[0][9..14], [0x10, 0x80, 0x01, 0x80, 0x04]);
}

#[test]
fn function_groups() {
    let mut sim = Sim::new();
    sim.set_flags(1, BC_DRIVE_SWITCH | BC_ALL_LOCOS);
    // F0 and F2, F5–F8, F9–F12, F13–F20, F21–F28, F29–F31.
    let groups = [
        (0x20, 0x12),
        (0x21, 0x0F),
        (0x22, 0x0A),
        (0x23, 0x81),
        (0x28, 0xFF),
        (0x29, 0x05),
    ];
    for (group, bits) in groups {
        sim.ask(1, &loco_request(0xE4, group, 3, bits));
    }
    let reply = sim.ask(1, &x_dataset(&[0xE3, 0xF0, 0x00, 0x03]));
    assert_eq!(reply[0][9..14], [0x12, 0xAF, 0x81, 0xFF, 0x05]);

    // A group replaces only its own functions.
    sim.ask(1, &loco_request(0xE4, 0x20, 3, 0x00));
    let reply = sim.ask(1, &x_dataset(&[0xE3, 0xF0, 0x00, 0x03]));
    assert_eq!(reply[0][9..14], [0x00, 0xAF, 0x81, 0xFF, 0x05]);

    // F32 and up reach the track only, without feedback (spec 4.3.2, note D).
    assert!(sim.ask(1, &loco_request(0xE4, 0x2A, 3, 0xFF)).is_empty());
}

#[test]
fn loco_emergency_stop() {
    let mut sim = Sim::new();
    sim.set_flags(1, BC_DRIVE_SWITCH | BC_ALL_LOCOS);
    sim.ask(1, &loco_request(0xE4, 0x13, 3, 0x94));
    let reply = sim.ask(1, &x_dataset(&[0x92, 0x00, 0x03]));
    assert_eq!(reply[0][8], 0x81);

    // MM locos get step 0 instead (spec 4.5) and carry the M bit.
    sim.ask(1, &[0x07, 0x00, 0x61, 0x00, 0x00, 0x05, 0x01]);
    sim.ask(1, &loco_request(0xE4, 0x12, 5, 0x05));
    let reply = sim.ask(1, &x_dataset(&[0x92, 0x00, 0x05]));
    assert_eq!(reply[0][7..9], [0x12, 0x00]);
}

#[test]
fn long_address() {
    let mut sim = Sim::new();
    // Address 1234 = 0x04D2, sent with the two top bits of DB1 set.
    let reply = sim.ask(1, &x_dataset(&[0xE3, 0xF0, 0xC4, 0xD2]));
    assert_eq!(reply[0][5..7], [0x04, 0xD2]);
}

#[test]
fn at_most_16_subscriptions() {
    let mut sim = Sim::new();
    sim.set_flags(1, BC_DRIVE_SWITCH);
    for address in 1..=17 {
        sim.ask(1, &x_dataset(&[0xE3, 0xF0, 0x00, address]));
    }
    // Loco 1 was dropped first in, loco 2 is still subscribed.
    assert!(received(&sim.send(2, &loco_request(0xE4, 0x13, 1, 0x90)), 1).is_empty());
    assert_eq!(
        received(&sim.send(2, &loco_request(0xE4, 0x13, 2, 0x90)), 1).len(),
        1
    );
}

// Clients (spec 1.1, 2.2, 2.7–2.18).

#[test]
fn track_power_reaches_clients_with_flag() {
    let mut sim = Sim::new();
    sim.set_flags(1, BC_DRIVE_SWITCH);
    sim.ask(2, &[0x04, 0x00, 0x10, 0x00]);
    sim.set_flags(3, BC_SYSTEM_STATE);

    let sent = sim.send(4, &[0x07, 0x00, 0x40, 0x00, 0x21, 0x80, 0xa1]);
    let power_off = [0x07, 0x00, 0x40, 0x00, 0x61, 0x00, 0x61];
    assert_eq!(received(&sent, 1), [power_off]);
    assert!(received(&sent, 2).is_empty());
    assert_eq!(received(&sent, 3)[0][..4], [0x14, 0x00, 0x84, 0x00]);
    assert_eq!(received(&sent, 4), [power_off]);

    // No system state broadcast if nothing changed.
    let sent = sim.send(4, &[0x07, 0x00, 0x40, 0x00, 0x21, 0x80, 0xa1]);
    assert!(received(&sent, 3).is_empty());
}

#[test]
fn logoff_ends_broadcasts() {
    let mut sim = Sim::new();
    sim.set_flags(1, BC_DRIVE_SWITCH);
    assert!(sim.ask(1, &[0x04, 0x00, 0x30, 0x00]).is_empty());
    let sent = sim.send(2, &[0x06, 0x00, 0x40, 0x00, 0x80, 0x80]);
    assert!(received(&sent, 1).is_empty());
    // Flags must be set again after the next login (spec 2.16).
    assert_eq!(
        sim.ask(1, &[0x04, 0x00, 0x51, 0x00]),
        [[0x08, 0x00, 0x51, 0x00, 0, 0, 0, 0]]
    );
}

#[test]
fn silent_clients_time_out() {
    let mut sim = Sim::new();
    sim.set_flags(1, BC_DRIVE_SWITCH);
    sim.set_flags(2, BC_DRIVE_SWITCH);
    sim.now += Duration::from_secs(60);
    sim.ask(2, &[0x04, 0x00, 0x10, 0x00]);
    sim.now += Duration::from_secs(1);
    let sent = sim.send(3, &[0x06, 0x00, 0x40, 0x00, 0x80, 0x80]);
    assert!(received(&sent, 1).is_empty());
    assert_eq!(received(&sent, 2).len(), 1);
}
