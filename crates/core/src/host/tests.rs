use super::*;
use crate::audio::tests::{LogSink, Played};
use crate::decoder::Decoder;
use crate::driving_sound::SoundState;
use crate::function::{Function, Mode};
use crate::input::Target;
use crate::sound::{Engine, EngineSound};
use crate::station::{LocoState, StationKind};
use std::sync::{Arc, Mutex};
use tempfile::TempDir;

/// Events the test hands to the fake driver.
type Events = Arc<Mutex<Vec<StationEvent>>>;

/// What the fake driver got; locos by address.
#[derive(Debug, PartialEq)]
pub(super) enum Call {
    Power(bool),
    Loco(u16, LocoState),
    EmergencyStop(u16),
}

type Sent = Arc<Mutex<Vec<Call>>>;

struct FakeDriver(Events, Sent);

impl CommandStation for FakeDriver {
    fn set_power(&mut self, on: bool) -> Result<(), StationError> {
        self.1.lock().unwrap().push(Call::Power(on));
        Ok(())
    }

    fn set_loco(&mut self, decoder: &Decoder, state: &LocoState) -> Result<(), StationError> {
        self.1
            .lock()
            .unwrap()
            .push(Call::Loco(decoder.address(), *state));
        Ok(())
    }

    fn emergency_stop(&mut self, decoder: &Decoder, _: &LocoState) -> Result<(), StationError> {
        self.1
            .lock()
            .unwrap()
            .push(Call::EmergencyStop(decoder.address()));
        Ok(())
    }

    fn events(&mut self) -> Vec<StationEvent> {
        std::mem::take(&mut self.0.lock().unwrap())
    }
}

/// A host whose connector reaches only the server "srcp", its events, the
/// loco states the driver got and its library, deleted when dropped. The
/// sound "idle" lasts one second, no other sound plays.
pub(super) fn host() -> (Host, Events, Sent, TempDir) {
    let audio = LogSink::new(&[("idle", 1.0)]);
    let (events, sent) = (Events::default(), Sent::default());
    let library = TempDir::new().unwrap();
    let (driver_events, driver_sent) = (Arc::clone(&events), Arc::clone(&sent));
    let connector: Connector = Box::new(move |station| {
        if station.host == "srcp" {
            let driver = FakeDriver(Arc::clone(&driver_events), Arc::clone(&driver_sent));
            Ok(Box::new(driver))
        } else {
            Err(StationError(format!("cannot reach {}", station.host)))
        }
    });
    let host = Host::new(connector, Box::new(audio), library.path().into()).unwrap();
    (host, events, sent, library)
}

pub(super) fn set_server(host: &mut Host, name: &str) -> Result<(), CommandError> {
    host.apply(Command::SetServer {
        kind: StationKind::Srcp,
        host: name.into(),
        port: 4303,
        bus: 2,
    })
}

#[test]
fn the_server_defaults_to_electrip_1() {
    let (host, _, _, _library) = host();
    let station = host.session().station();
    assert_eq!(
        (station.host.as_str(), station.port, station.bus),
        ("localhost", 4303, 1)
    );
    assert!(!station.connected);
}

#[test]
fn connects_to_the_configured_server() {
    let (mut host, _, _, _library) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    let station = host.session().station();
    assert_eq!((station.host.as_str(), station.bus), ("srcp", 2));
    assert!(station.connected);
}

#[test]
fn a_failed_connect_reports_the_error_and_changes_nothing() {
    let (mut host, _, _, _library) = host();
    let before = host.session().clone();
    let error = host.apply(Command::Connect).unwrap_err();
    assert_eq!(error.to_string(), "cannot reach localhost");
    assert_eq!(*host.session(), before);
}

#[test]
fn the_server_changes_only_while_disconnected() {
    let (mut host, _, _, _library) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    assert_eq!(set_server(&mut host, "other"), Err(CommandError::Connected));
    host.apply(Command::Disconnect).unwrap();
    assert!(!host.session().station().connected);
    set_server(&mut host, "other").unwrap();
}

#[test]
fn a_broken_connection_disconnects_and_can_be_reopened() {
    let (mut host, events, _, _library) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    assert!(!host.poll(0.05));
    events.lock().unwrap().push(StationEvent::Disconnected);
    assert!(host.poll(0.05));
    assert!(!host.session().station().connected);
    host.apply(Command::Connect).unwrap();
    assert!(host.session().station().connected);
}

/// A connected host with one loco (id 1, address 1, 100 km/h, 128 steps,
/// 11.5 s to accelerate) and what the driver got after connecting.
fn driving_host() -> (Host, Sent, TempDir) {
    let (mut host, _, sent, library) = host();
    host.apply(Command::AddLoco).unwrap();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    sent.lock().unwrap().clear();
    (host, sent, library)
}

fn set_axis(host: &mut Host, deflection: f64) {
    host.apply(Command::SetAxis {
        loco: 1,
        deflection,
    })
    .unwrap();
}

fn speed(host: &Host) -> f64 {
    host.session().locos()[0].motion.speed()
}

fn state(forward: bool, step: u8) -> Call {
    let state = LocoState {
        forward,
        step,
        functions: 0,
    };
    Call::Loco(1, state)
}

#[test]
fn the_axis_accelerates_and_the_driver_gets_the_speed_step() {
    let (mut host, sent, _library) = driving_host();
    assert!(!host.poll(0.05));
    set_axis(&mut host, 1.0);
    assert!(host.poll(1.15));
    assert!((speed(&host) - 10.0).abs() < 1e-9);
    assert!(host.poll(20.0));
    assert_eq!(speed(&host), 100.0);
    assert_eq!(*sent.lock().unwrap(), [state(true, 12), state(true, 128)]);
}

#[test]
fn the_axis_at_rest_keeps_the_speed_and_sends_nothing() {
    let (mut host, sent, _library) = driving_host();
    set_axis(&mut host, 1.0);
    host.poll(2.3);
    set_axis(&mut host, 0.03);
    sent.lock().unwrap().clear();
    assert!(!host.poll(1.0));
    assert!((speed(&host) - 20.0).abs() < 1e-9);
    assert!(sent.lock().unwrap().is_empty());
}

#[test]
fn the_axis_back_brakes() {
    let (mut host, _, _library) = driving_host();
    set_axis(&mut host, 1.0);
    host.poll(11.5);
    set_axis(&mut host, -0.5);
    host.poll(8.5);
    assert!((speed(&host) - 50.0).abs() < 1e-9);
}

#[test]
fn reverse_stops_and_changes_the_direction() {
    let (mut host, sent, _library) = driving_host();
    host.apply(Command::Reverse { loco: 1 }).unwrap();
    host.poll(0.05);
    set_axis(&mut host, 1.0);
    host.poll(11.5);
    host.apply(Command::Reverse { loco: 1 }).unwrap();
    set_axis(&mut host, 0.0);
    host.poll(0.05);
    assert_eq!(
        *sent.lock().unwrap(),
        [state(false, 0), state(false, 128), state(true, 0)]
    );
}

#[test]
fn locos_drive_without_a_connection() {
    let (mut host, _, _, _library) = host();
    host.apply(Command::AddLoco).unwrap();
    set_axis(&mut host, 1.0);
    assert!(host.poll(11.5));
    assert_eq!(speed(&host), 100.0);
}

#[test]
fn the_axis_of_an_unknown_loco_is_an_error() {
    let (mut host, _, _, _library) = host();
    let error = host.apply(Command::SetAxis {
        loco: 7,
        deflection: 1.0,
    });
    assert_eq!(error, Err(CommandError::UnknownLoco(7)));
    let error = host.apply(Command::Reverse { loco: 7 });
    assert_eq!(error, Err(CommandError::UnknownLoco(7)));
}

#[test]
fn connecting_switches_the_track_power_on() {
    let (mut host, _, sent, _library) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    assert!(host.session().station().track_power);
    assert_eq!(*sent.lock().unwrap(), [Call::Power(true)]);
    host.apply(Command::Disconnect).unwrap();
    assert!(!host.session().station().track_power);
}

#[test]
fn connecting_leaves_the_track_power_if_switched_off() {
    let (mut host, _, sent, _library) = host();
    assert!(host.session().station().power_on_start);
    host.apply(Command::SetPowerOnStart { on: false }).unwrap();
    set_server(&mut host, "srcp").unwrap();
    assert!(!host.session().station().power_on_start);
    host.apply(Command::Connect).unwrap();
    assert!(!host.session().station().track_power);
    assert!(sent.lock().unwrap().is_empty());
}

#[test]
fn the_emergency_stop_toggles_the_track_power() {
    let (mut host, sent, _library) = driving_host();
    host.apply(Command::TogglePower).unwrap();
    assert!(!host.session().station().track_power);
    host.apply(Command::TogglePower).unwrap();
    assert!(host.session().station().track_power);
    assert_eq!(
        *sent.lock().unwrap(),
        [Call::Power(false), Call::Power(true)]
    );
}

#[test]
fn the_track_power_toggles_only_while_connected() {
    let (mut host, _, _, _library) = host();
    let error = host.apply(Command::TogglePower);
    assert_eq!(error, Err(CommandError::Disconnected));
}

#[test]
fn the_track_power_follows_the_command_station() {
    let (mut host, events, _, _library) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    events.lock().unwrap().push(StationEvent::Power(false));
    assert!(host.poll(0.05));
    assert!(!host.session().station().track_power);
}

#[test]
fn the_loco_emergency_stop_stops_only_the_loco() {
    let (mut host, sent, _library) = driving_host();
    set_axis(&mut host, 1.0);
    host.poll(11.5);
    sent.lock().unwrap().clear();
    host.apply(Command::EmergencyStop { loco: 1 }).unwrap();
    host.poll(1.0);
    assert_eq!(speed(&host), 0.0);
    assert!(host.session().station().track_power);
    assert_eq!(*sent.lock().unwrap(), [Call::EmergencyStop(1)]);
}

/// A connected host with `locos` locos (ids from 1, addresses 1) and one
/// pad (id 1) with the standard mapping.
fn host_with_pad(locos: usize) -> (Host, Sent, TempDir) {
    let (mut host, sent, library) = driving_host();
    for _ in 1..locos {
        host.apply(Command::AddLoco).unwrap();
    }
    add_device(&mut host, 1);
    (host, sent, library)
}

/// Gives each loco a combustion engine with only an idle sound.
fn add_idle_sound(host: &mut Host) {
    for loco in 1..=host.session().locos().len() as u32 {
        let engine = Some(Engine::Diesel);
        let (sound, path) = (EngineSound::Idle, Some("idle".into()));
        host.apply(Command::SetEngine {
            loco,
            engine,
            confirmed: false,
        })
        .unwrap();
        host.apply(Command::SetEngineSound { loco, sound, path })
            .unwrap();
    }
}

fn sound_states(host: &Host) -> Vec<SoundState> {
    let locos = host.session().locos();
    locos.iter().map(|e| e.sound.state()).collect()
}

fn add_device(host: &mut Host, device: u32) {
    let kind = "pad".into();
    host.apply(Command::AddDevice { device, kind }).unwrap();
}

fn input(host: &mut Host, control: &str, value: f64) -> Result<(), CommandError> {
    host.apply(Command::Input {
        device: 1,
        control: control.into(),
        value,
    })
}

fn press(host: &mut Host, control: &str) {
    input(host, control, 1.0).unwrap();
    input(host, control, 0.0).unwrap();
}

fn device_loco(host: &Host, device: usize) -> Option<u32> {
    host.session().devices()[device].loco
}

#[test]
fn the_axis_of_a_device_drives_its_loco_with_up_negative() {
    let (mut host, _, _library) = host_with_pad(1);
    input(&mut host, "lefty", -1.0).unwrap();
    host.poll(1.15);
    assert!((speed(&host) - 10.0).abs() < 1e-9);
}

#[test]
fn the_dead_zone_belongs_to_the_binding() {
    let (mut host, _, _library) = host_with_pad(1);
    input(&mut host, "lefty", -0.1).unwrap();
    host.poll(1.0);
    assert!(speed(&host) > 0.0);
    bind(&mut host, "lefty", Target::Drive { dead_zone: 0.2 });
    let before = speed(&host);
    input(&mut host, "lefty", -0.1).unwrap();
    host.poll(1.0);
    assert_eq!(speed(&host), before);
}

#[test]
fn buttons_trigger_built_in_actions_once_per_press() {
    let (mut host, sent, _library) = host_with_pad(1);
    input(&mut host, "a", 1.0).unwrap();
    input(&mut host, "a", 1.0).unwrap();
    assert!(!host.session().station().track_power);
    input(&mut host, "a", 0.0).unwrap();
    press(&mut host, "b");
    assert!(!host.session().locos()[0].motion.forward());
    assert_eq!(*sent.lock().unwrap(), [Call::Power(false)]);
}

fn bind(host: &mut Host, control: &str, target: Target) {
    let (kind, control) = ("pad".into(), control.into());
    host.apply(Command::Bind {
        kind,
        control,
        target,
    })
    .unwrap();
}

#[test]
fn focus_holds_while_the_button_is_down() {
    let (mut host, _, _library) = host_with_pad(1);
    bind(&mut host, "x", Target::Focus);
    input(&mut host, "x", 1.0).unwrap();
    assert!(host.session().devices()[0].focus);
    input(&mut host, "x", 0.0).unwrap();
    assert!(!host.session().devices()[0].focus);
}

#[test]
fn toggle_sound_switches_the_sound_of_the_device_loco() {
    let (mut host, _, _library) = host_with_pad(2);
    add_idle_sound(&mut host);
    bind(&mut host, "y", Target::ToggleSound);
    use SoundState::*;
    assert_eq!(sound_states(&host), [Off, Off]);
    press(&mut host, "y");
    assert_eq!(sound_states(&host), [Starting, Off]);
    host.poll(1.0);
    assert_eq!(sound_states(&host), [On, Off]);
    press(&mut host, "y");
    assert_eq!(sound_states(&host), [Stopping, Off]);
    host.poll(1.0);
    assert_eq!(sound_states(&host), [Stopping, Off]);
    host.poll(1.0);
    assert_eq!(sound_states(&host), [Off, Off]);
}

#[test]
fn axes_and_hat_directions_trigger_built_in_actions_like_buttons() {
    let (mut host, _, _library) = host_with_pad(1);
    bind(&mut host, "righttrigger", Target::ToggleSound);
    bind(&mut host, "dpup", Target::Reverse);
    add_idle_sound(&mut host);
    input(&mut host, "righttrigger", 0.4).unwrap();
    assert_eq!(sound_states(&host), [SoundState::Off]);
    input(&mut host, "righttrigger", 1.0).unwrap();
    assert_eq!(sound_states(&host), [SoundState::Starting]);
    press(&mut host, "dpup");
    assert!(!host.session().locos()[0].motion.forward());
}

#[test]
fn a_control_without_binding_does_nothing() {
    let (mut host, _, _library) = host_with_pad(1);
    let before = host.session().clone();
    press(&mut host, "x");
    assert_eq!(*host.session(), before);
}

#[test]
fn a_bound_action_switches_the_functions_of_the_device_loco() {
    let (mut host, _, _library) = host_with_pad(2);
    host.apply(Command::AddAction {
        name: "Licht".into(),
    })
    .unwrap();
    for loco in [1, 2] {
        let function = Function {
            action: 1,
            number: 0,
            name: String::new(),
            mode: Mode::Push,
            default_on: false,
            on: false,
        };
        host.apply(Command::AddFunction { loco, function }).unwrap();
    }
    bind(&mut host, "x", Target::Action { action: 1 });
    input(&mut host, "x", 1.0).unwrap();
    let on = |host: &Host| {
        host.session()
            .locos()
            .iter()
            .map(|e| e.loco.functions()[0].on)
            .collect::<Vec<_>>()
    };
    assert_eq!(on(&host), [true, false]);
    input(&mut host, "x", 0.0).unwrap();
    assert_eq!(on(&host), [false, false]);
}

#[test]
fn devices_get_free_locos_and_skip_taken_ones_when_changing() {
    let (mut host, _, _library) = host_with_pad(3);
    add_device(&mut host, 2);
    assert_eq!(
        (device_loco(&host, 0), device_loco(&host, 1)),
        (Some(1), Some(2))
    );
    press(&mut host, "dpright");
    assert_eq!(device_loco(&host, 0), Some(3));
    press(&mut host, "dpright");
    assert_eq!(device_loco(&host, 0), Some(3));
    press(&mut host, "dpleft");
    assert_eq!(device_loco(&host, 0), Some(1));
}

#[test]
fn each_device_gets_the_lowest_free_color_up_to_twelve() {
    let (mut host, _, _library) = host_with_pad(1);
    for device in 2..=12 {
        add_device(&mut host, device);
    }
    let colors = |host: &Host| -> Vec<u8> {
        let devices = host.session().devices();
        devices.iter().map(|d| d.color).collect()
    };
    assert_eq!(colors(&host), (1..=12).collect::<Vec<_>>());
    let (device, kind) = (13, "pad".to_string());
    let thirteenth = Command::AddDevice { device, kind };
    assert_eq!(
        host.apply(thirteenth.clone()),
        Err(CommandError::TooManyDevices)
    );
    host.apply(Command::RemoveDevice { device: 5 }).unwrap();
    host.apply(thirteenth).unwrap();
    assert_eq!(colors(&host).last(), Some(&5));
}

#[test]
fn holding_next_loco_scrolls_until_released() {
    let (mut host, _, _library) = host_with_pad(5);
    add_device(&mut host, 2);
    input(&mut host, "dpright", 1.0).unwrap();
    assert_eq!(device_loco(&host, 0), Some(3));
    assert!(!host.poll(0.45));
    assert!(host.poll(0.12));
    assert_eq!(device_loco(&host, 0), Some(4));
    host.poll(0.06);
    assert_eq!(device_loco(&host, 0), Some(5));
    input(&mut host, "dpright", 0.0).unwrap();
    input(&mut host, "dpleft", 1.0).unwrap();
    input(&mut host, "dpleft", 0.0).unwrap();
    host.poll(1.0);
    assert_eq!(device_loco(&host, 0), Some(4));
}

#[test]
fn releasing_stops_the_scroll_even_after_unbinding() {
    let (mut host, _, _library) = host_with_pad(3);
    input(&mut host, "dpright", 1.0).unwrap();
    let (kind, control) = ("pad".into(), "dpright".into());
    host.apply(Command::Unbind { kind, control }).unwrap();
    input(&mut host, "dpright", 0.0).unwrap();
    host.poll(1.0);
    assert_eq!(device_loco(&host, 0), Some(2));
}

#[test]
fn the_axis_moves_along_to_the_new_loco() {
    let (mut host, _, _library) = host_with_pad(2);
    input(&mut host, "lefty", -1.0).unwrap();
    press(&mut host, "dpright");
    host.poll(1.15);
    let speeds: Vec<f64> = host
        .session()
        .locos()
        .iter()
        .map(|e| e.motion.speed())
        .collect();
    assert_eq!(speeds[0], 0.0);
    assert!((speeds[1] - 10.0).abs() < 1e-9);
}

#[test]
fn removing_a_device_releases_the_axis_of_its_loco() {
    let (mut host, _, _library) = host_with_pad(1);
    input(&mut host, "lefty", -1.0).unwrap();
    host.poll(1.15);
    host.apply(Command::RemoveDevice { device: 1 }).unwrap();
    host.poll(1.0);
    assert!((speed(&host) - 10.0).abs() < 1e-9);
    assert_eq!(
        input(&mut host, "a", 1.0),
        Err(CommandError::UnknownDevice(1))
    );
}

#[test]
fn a_removed_loco_frees_the_device_for_another() {
    let (mut host, _, _library) = host_with_pad(2);
    add_device(&mut host, 2);
    host.apply(Command::AddLoco).unwrap();
    host.apply(Command::RemoveLoco { loco: 1 }).unwrap();
    assert_eq!(
        (device_loco(&host, 0), device_loco(&host, 1)),
        (Some(3), Some(2))
    );
}

#[test]
fn removing_an_action_removes_its_bindings() {
    let (mut host, _, _library) = host_with_pad(1);
    host.apply(Command::AddAction {
        name: "Licht".into(),
    })
    .unwrap();
    bind(&mut host, "x", Target::Action { action: 1 });
    host.apply(Command::RemoveAction { action: 1 }).unwrap();
    assert_eq!(host.session().mappings()[0].target("x"), None);
}

#[test]
fn device_ids_are_unique() {
    let (mut host, _, _library) = host_with_pad(1);
    let kind = "other".into();
    let error = host.apply(Command::AddDevice { device: 1, kind });
    assert_eq!(error, Err(CommandError::DeviceExists(1)));
}

#[test]
fn the_speed_stays_while_the_engine_starts() {
    let (mut host, _, _library) = driving_host();
    add_idle_sound(&mut host);
    set_axis(&mut host, 1.0);
    host.apply(Command::ToggleSound { loco: 1 }).unwrap();
    host.poll(0.5);
    assert_eq!(speed(&host), 0.0);
    host.poll(0.5);
    host.poll(0.5);
    assert!(speed(&host) > 0.0);
}

/// A host with one loco, a pad (id 1) whose "x" triggers the action
/// "Hupe" (1), and the log of its audio target, where "horn" lasts one
/// second.
fn host_with_horn(mode: &str) -> (Host, Played, TempDir) {
    let audio = LogSink::new(&[("horn", 1.0)]);
    let played = Arc::clone(&audio.played);
    let library = TempDir::new().unwrap();
    let connector: Connector = Box::new(|_| Err(StationError("offline".into())));
    let mut host = Host::new(connector, Box::new(audio), library.path().into()).unwrap();
    host.apply(Command::AddLoco).unwrap();
    add_device(&mut host, 1);
    let name = "Hupe".into();
    host.apply(Command::AddAction { name }).unwrap();
    let function = serde_json::json!({"action": 1, "mode": mode, "path": "horn"});
    let function = serde_json::from_value(function).unwrap();
    host.apply(Command::AddSoundFunction { loco: 1, function })
        .unwrap();
    bind(&mut host, "x", Target::Action { action: 1 });
    (host, played, library)
}

fn take(played: &Played) -> Vec<String> {
    std::mem::take(&mut played.lock().unwrap())
}

#[test]
fn a_bound_action_plays_the_sound_functions_of_the_device_loco() {
    let (mut host, played, _library) = host_with_horn("switch");
    press(&mut host, "x");
    assert_eq!(take(&played), ["1.10001 horn", "1.10001 horn"]);
    host.poll(1.0);
    assert_eq!(take(&played), ["1.10001 horn"]);
    press(&mut host, "x");
    assert_eq!(take(&played), ["1.10001 stop"]);
}

#[test]
fn a_tapped_sound_function_switches_off_at_the_end() {
    let (mut host, played, _library) = host_with_horn("tap");
    let on = |host: &Host| host.session().locos()[0].loco.sound_functions()[0].on;
    press(&mut host, "x");
    assert!(on(&host));
    assert!(!host.poll(0.5));
    press(&mut host, "x");
    assert!(host.poll(0.5));
    assert!(!on(&host));
    assert_eq!(take(&played), ["1.10001 horn"]);
}
