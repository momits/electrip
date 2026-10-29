//! Loco state and its encoding in LAN_X_LOCO_INFO (spec chapter 4).

/// Function groups of LAN_X_SET_LOCO_FUNCTION_GROUP with feedback to LAN
/// clients: group byte, first function, number of functions (spec 4.3.2).
/// Group 0x20 holds F0 in bit 4 and F1–F4 in bits 0–3, see `group_bits`.
const GROUPS: [(u8, u32, u32); 6] = [
    (0x20, 0, 5),
    (0x21, 5, 4),
    (0x22, 9, 4),
    (0x23, 13, 8),
    (0x28, 21, 8),
    (0x29, 29, 3),
];

/// Groups for F32–F68: the Z21 sends them to the track only, without
/// feedback to LAN clients (spec 4.3.2, note D).
pub const GROUPS_WITHOUT_FEEDBACK: [u8; 4] = [0x2A, 0x2B, 0x50, 0x51];

#[derive(Clone, Copy, PartialEq, Debug)]
pub struct Loco {
    /// Speed step format KKK: 0 = 14, 2 = 28, 4 = 128 steps.
    pub steps: u8,
    /// RVVVVVVV: direction bit and speed, coded as in LAN_X_SET_LOCO_DRIVE.
    pub speed: u8,
    /// Bit n is function Fn, for F0–F31.
    pub functions: u32,
}

impl Default for Loco {
    /// The spec does not say what a new loco reports; the simulator assumes
    /// 128 steps, stopped, reverse, all functions off.
    fn default() -> Self {
        Loco {
            steps: 4,
            speed: 0,
            functions: 0,
        }
    }
}

impl Loco {
    /// Applies the speed step byte 0x1S of LAN_X_SET_LOCO_DRIVE.
    /// Returns false for an unknown S.
    pub fn drive(&mut self, format: u8, speed: u8) -> bool {
        self.steps = match format {
            0x10 => 0,
            0x12 => 2,
            0x13 => 4,
            _ => return false,
        };
        self.speed = speed;
        true
    }

    /// Emergency stop of LAN_X_SET_LOCO_E_STOP: speed code E-Stop, which is
    /// 1 in every DCC format, direction kept. MM locos get step 0 (spec 4.5).
    pub fn emergency_stop(&mut self, mm: bool) {
        self.speed = (self.speed & 0x80) | u8::from(!mm);
    }

    /// Applies TTNNNNNN of LAN_X_SET_LOCO_FUNCTION.
    /// Returns false for TT = 11 or a function above F31.
    pub fn switch_function(&mut self, code: u8) -> bool {
        let index = code & 0x3F;
        if index > 31 {
            return false;
        }
        let bit = 1u32 << index;
        match code >> 6 {
            0 => self.functions &= !bit,
            1 => self.functions |= bit,
            2 => self.functions ^= bit,
            _ => return false,
        }
        true
    }

    /// Applies LAN_X_SET_LOCO_FUNCTION_GROUP. Returns false for a group
    /// without feedback or an unknown group.
    pub fn set_group(&mut self, group: u8, bits: u8) -> bool {
        let Some(&(_, first, count)) = GROUPS.iter().find(|g| g.0 == group) else {
            return false;
        };
        let mask = ((1u32 << count) - 1) << first;
        let value = (group_bits(group, bits) << first) & mask;
        self.functions = (self.functions & !mask) | value;
        true
    }

    /// Lok-Information of LAN_X_LOCO_INFO, DB0 to DB8 (spec 4.4).
    /// The function bytes follow the same layout as `GROUPS`.
    pub fn info(&self, address: u16, mm: bool) -> [u8; 9] {
        let f = self.functions;
        let [msb, lsb] = address.to_be_bytes();
        [
            msb & 0x3F,
            lsb,
            u8::from(mm) << 4 | self.steps,
            self.speed,
            ((f >> 1) & 0x0F) as u8 | ((f & 1) as u8) << 4,
            (f >> 5) as u8,
            (f >> 13) as u8,
            (f >> 21) as u8,
            ((f >> 29) & 0x07) as u8,
        ]
    }
}

/// Function bits of a group in the order Fn, Fn+1, … from bit 0.
fn group_bits(group: u8, bits: u8) -> u32 {
    let bits = u32::from(bits);
    if group == 0x20 {
        (bits & 0x0F) << 1 | (bits >> 4) & 1
    } else {
        bits
    }
}
