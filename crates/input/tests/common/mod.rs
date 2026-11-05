//! Virtual gamepads and joysticks of SDL, and a host that executes the
//! commands of [`Gamepads`]. SDL is global to the process, so each test
//! file holds one test.

// Test code: unwrap is allowed (AGENTS.md); not every test uses every helper.
#![allow(clippy::unwrap_used, dead_code)]

use electrip_core::audio::AudioSink;
use electrip_core::decoder::Decoder;
use electrip_core::host::Host;
use electrip_core::session::LocoEntry;
use electrip_core::station::{CommandStation, LocoState, StationError, StationEvent};
use electrip_input::Gamepads;
use sdl3_sys::everything::*;
use serde_json::Value;
use std::ffi::CStr;
use std::path::Path;
use tempfile::TempDir;

/// An audio target where every sound lasts one second.
struct Audio;

impl AudioSink for Audio {
    fn length(&mut self, _: &Path) -> Result<f64, String> {
        Ok(1.0)
    }

    fn queue(&mut self, _: u32, _: &Path) {}

    fn stop(&mut self, _: u32) {}
}

/// SDL, a connected host and its library.
pub struct Rig {
    pub gamepads: Gamepads,
    pub host: Host,
    _library: TempDir,
}

impl Rig {
    pub fn new() -> Rig {
        let library = TempDir::new().unwrap();
        let connect = Box::new(|_: &_| Ok(Box::new(Station) as _));
        let mut host = Host::new(connect, Box::new(Audio), library.path().into()).unwrap();
        host.apply(serde_json::from_str(r#"{"command": "connect"}"#).unwrap())
            .unwrap();
        Rig {
            gamepads: Gamepads::open().unwrap(),
            host,
            _library: library,
        }
    }

    pub fn apply(&mut self, command: Value) {
        self.host
            .apply(serde_json::from_value(command).unwrap())
            .unwrap();
    }

    /// Executes the commands from the devices, then drives the locos for
    /// `seconds`.
    pub fn update(&mut self, seconds: f64) {
        for command in self.gamepads.poll() {
            self.host.apply(command).unwrap();
        }
        self.host.poll(seconds);
    }

    pub fn loco(&self, id: u32) -> &LocoEntry {
        self.host
            .session()
            .locos()
            .iter()
            .find(|e| e.id == id)
            .unwrap()
    }

    /// The loco each device controls, by device kind.
    pub fn devices(&self) -> Vec<(String, Option<u32>)> {
        let devices = self.host.session().devices();
        devices.iter().map(|d| (d.kind.clone(), d.loco)).collect()
    }

    pub fn colors(&self) -> Vec<u8> {
        let devices = self.host.session().devices();
        devices.iter().map(|d| d.color).collect()
    }
}

/// A command station that accepts everything.
struct Station;

impl CommandStation for Station {
    fn set_power(&mut self, _: bool) -> Result<(), StationError> {
        Ok(())
    }

    fn set_loco(&mut self, _: &Decoder, _: &LocoState) -> Result<(), StationError> {
        Ok(())
    }

    fn emergency_stop(&mut self, _: &Decoder, _: &LocoState) -> Result<(), StationError> {
        Ok(())
    }

    fn events(&mut self) -> Vec<StationEvent> {
        Vec::new()
    }
}

/// A virtual device of SDL; SDL must be open.
pub struct Virtual {
    pub id: SDL_JoystickID,
    joystick: *mut SDL_Joystick,
}

impl Virtual {
    /// A gamepad that SDL knows by its USB vendor and product id.
    pub fn gamepad(name: &CStr, vendor: u16, product: u16) -> Virtual {
        Virtual::attach(SDL_VirtualJoystickDesc {
            r#type: SDL_JOYSTICK_TYPE_GAMEPAD.0 as u16,
            vendor_id: vendor,
            product_id: product,
            naxes: SDL_GAMEPAD_AXIS_COUNT.0 as u16,
            nbuttons: SDL_GAMEPAD_BUTTON_COUNT.0 as u16,
            name: name.as_ptr(),
            ..SDL_VirtualJoystickDesc::new()
        })
    }

    /// A joystick with numbered controls.
    pub fn joystick(name: &CStr, axes: u16, buttons: u16, hats: u16) -> Virtual {
        Virtual::attach(SDL_VirtualJoystickDesc {
            r#type: SDL_JOYSTICK_TYPE_FLIGHT_STICK.0 as u16,
            naxes: axes,
            nbuttons: buttons,
            nhats: hats,
            name: name.as_ptr(),
            ..SDL_VirtualJoystickDesc::new()
        })
    }

    fn attach(desc: SDL_VirtualJoystickDesc) -> Virtual {
        unsafe {
            let id = SDL_AttachVirtualJoystick(&desc);
            assert_ne!(id.0, 0, "{:?}", CStr::from_ptr(SDL_GetError()));
            let joystick = SDL_OpenJoystick(id);
            assert!(!joystick.is_null());
            Virtual { id, joystick }
        }
    }

    /// Full deflection is 1 or -1.
    pub fn axis(&self, axis: SDL_GamepadAxis, value: f64) {
        self.joystick_axis(axis.0, value);
    }

    pub fn joystick_axis(&self, axis: i32, value: f64) {
        let value = (value * f64::from(SDL_JOYSTICK_AXIS_MAX)) as i16;
        assert!(unsafe { SDL_SetJoystickVirtualAxis(self.joystick, axis, value) });
    }

    pub fn button(&self, button: SDL_GamepadButton, down: bool) {
        self.joystick_button(button.0, down);
    }

    pub fn joystick_button(&self, button: i32, down: bool) {
        assert!(unsafe { SDL_SetJoystickVirtualButton(self.joystick, button, down) });
    }

    pub fn hat(&self, hat: i32, value: u8) {
        assert!(unsafe { SDL_SetJoystickVirtualHat(self.joystick, hat, value) });
    }

    /// Unplugs the device.
    pub fn detach(self) {
        unsafe {
            SDL_CloseJoystick(self.joystick);
            assert!(SDL_DetachVirtualJoystick(self.id));
        }
    }
}
