//! Gamepads and joysticks through SDL3 (N-01, B-03). SDL reports devices
//! and their controls as events; [`Gamepads::poll`] turns them into the
//! commands `add_device`, `remove_device` and `input` of the core.
//!
//! A device is a gamepad if SDL knows its layout (SDL mapping database);
//! its controls are then named like SDL names them (`a`, `lefty`,
//! `dpleft`). Other joysticks have numbered controls: `button0`, `axis1`
//! and the hat directions `hat0_up`, `hat0_right`, `hat0_down`, `hat0_left`.

use electrip_core::session::Command;
use sdl3_sys::everything::*;
use std::ffi::{CStr, c_char};

/// SDL with its gamepad subsystem; dropping it shuts SDL down.
pub struct Gamepads(());

impl Gamepads {
    /// Starts SDL. Devices already connected arrive as events with the
    /// first [`Gamepads::poll`].
    pub fn open() -> Result<Self, String> {
        // SAFETY: plain SDL calls; SDL_GetError returns a valid string.
        unsafe {
            // Otherwise SDL turns Ctrl+C into an event and the app keeps
            // running.
            SDL_SetHint(SDL_HINT_NO_SIGNAL_HANDLERS, c"1".as_ptr());
            if !SDL_Init(SDL_INIT_GAMEPAD) {
                return Err(format!("SDL: {}", string(SDL_GetError())));
            }
        }
        Ok(Gamepads(()))
    }

    /// The commands for all device events since the last call.
    pub fn poll(&mut self) -> Vec<Command> {
        let mut commands = Vec::new();
        let mut event = SDL_Event::default();
        // SAFETY: SDL fills the event; the union field read matches the
        // event type.
        while unsafe { SDL_PollEvent(&mut event) } {
            commands.extend(unsafe { translate(&event) });
        }
        commands
    }
}

impl Drop for Gamepads {
    fn drop(&mut self) {
        // SAFETY: SDL was initialized in `open`.
        unsafe { SDL_Quit() }
    }
}

/// The commands for one event.
///
/// # Safety
/// The event must come from SDL.
unsafe fn translate(event: &SDL_Event) -> Vec<Command> {
    let kind = SDL_EventType(unsafe { event.r#type });
    let input = |device: SDL_JoystickID, control: String, value: f64| Command::Input {
        device: device.0,
        control,
        value,
    };
    match kind {
        SDL_EVENT_JOYSTICK_ADDED => unsafe { add(event.jdevice.which) }.into_iter().collect(),
        SDL_EVENT_JOYSTICK_REMOVED => vec![unsafe { remove(event.jdevice.which) }],
        SDL_EVENT_GAMEPAD_AXIS_MOTION => {
            let e = unsafe { event.gaxis };
            let control =
                unsafe { string(SDL_GetGamepadStringForAxis(SDL_GamepadAxis(e.axis.into()))) };
            vec![input(e.which, control, axis(e.value))]
        }
        SDL_EVENT_GAMEPAD_BUTTON_DOWN | SDL_EVENT_GAMEPAD_BUTTON_UP => {
            let e = unsafe { event.gbutton };
            let button = SDL_GamepadButton(e.button.into());
            let control = unsafe { string(SDL_GetGamepadStringForButton(button)) };
            vec![input(e.which, control, button_value(e.down))]
        }
        // Gamepads report their controls twice, by name and by number.
        SDL_EVENT_JOYSTICK_AXIS_MOTION
        | SDL_EVENT_JOYSTICK_BUTTON_DOWN
        | SDL_EVENT_JOYSTICK_BUTTON_UP
        | SDL_EVENT_JOYSTICK_HAT_MOTION
            if unsafe { SDL_IsGamepad(event.jdevice.which) } =>
        {
            Vec::new()
        }
        SDL_EVENT_JOYSTICK_AXIS_MOTION => {
            let e = unsafe { event.jaxis };
            vec![input(e.which, format!("axis{}", e.axis), axis(e.value))]
        }
        SDL_EVENT_JOYSTICK_BUTTON_DOWN | SDL_EVENT_JOYSTICK_BUTTON_UP => {
            let e = unsafe { event.jbutton };
            let control = format!("button{}", e.button);
            vec![input(e.which, control, button_value(e.down))]
        }
        SDL_EVENT_JOYSTICK_HAT_MOTION => {
            let e = unsafe { event.jhat };
            HAT_DIRECTIONS
                .iter()
                .map(|(bit, name)| {
                    let control = format!("hat{}_{name}", e.hat);
                    input(e.which, control, button_value(e.value & bit != 0))
                })
                .collect()
        }
        _ => Vec::new(),
    }
}

/// Each hat direction is a button; diagonals press two of them.
const HAT_DIRECTIONS: [(u8, &str); 4] = [
    (SDL_HAT_UP, "up"),
    (SDL_HAT_RIGHT, "right"),
    (SDL_HAT_DOWN, "down"),
    (SDL_HAT_LEFT, "left"),
];

/// Opens the device, as a gamepad if SDL knows its layout. A device that
/// fails to open is left out.
unsafe fn add(id: SDL_JoystickID) -> Option<Command> {
    let name = unsafe {
        if SDL_IsGamepad(id) {
            SDL_GetGamepadName(SDL_OpenGamepad(id).as_mut()?)
        } else {
            SDL_GetJoystickName(SDL_OpenJoystick(id).as_mut()?)
        }
    };
    Some(Command::AddDevice {
        device: id.0,
        kind: unsafe { string(name) },
    })
}

unsafe fn remove(id: SDL_JoystickID) -> Command {
    unsafe {
        let gamepad = SDL_GetGamepadFromID(id);
        if gamepad.is_null() {
            SDL_CloseJoystick(SDL_GetJoystickFromID(id));
        } else {
            SDL_CloseGamepad(gamepad);
        }
    }
    Command::RemoveDevice { device: id.0 }
}

/// SDL axes go from -32768 to 32767; the core expects -1 to 1.
fn axis(value: i16) -> f64 {
    (f64::from(value) / f64::from(SDL_JOYSTICK_AXIS_MAX)).max(-1.0)
}

fn button_value(down: bool) -> f64 {
    if down { 1.0 } else { 0.0 }
}

/// A string from SDL; none is empty.
unsafe fn string(text: *const c_char) -> String {
    if text.is_null() {
        return String::new();
    }
    unsafe { CStr::from_ptr(text) }
        .to_string_lossy()
        .into_owned()
}
