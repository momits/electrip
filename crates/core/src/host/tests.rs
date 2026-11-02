use super::*;
use crate::decoder::Decoder;
use crate::station::LocoState;
use std::sync::{Arc, Mutex};

/// Events the test hands to the fake driver.
type Events = Arc<Mutex<Vec<StationEvent>>>;

/// What the fake driver got; locos by address.
#[derive(Debug, PartialEq)]
enum Call {
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

/// A host whose connector reaches only the server "srcp", its events and
/// the loco states the driver got.
fn host() -> (Host, Events, Sent) {
    let (events, sent) = (Events::default(), Sent::default());
    let (driver_events, driver_sent) = (Arc::clone(&events), Arc::clone(&sent));
    let host = Host::new(Box::new(move |station| {
        if station.host == "srcp" {
            let driver = FakeDriver(Arc::clone(&driver_events), Arc::clone(&driver_sent));
            Ok(Box::new(driver))
        } else {
            Err(StationError(format!("cannot reach {}", station.host)))
        }
    }));
    (host, events, sent)
}

fn set_server(host: &mut Host, name: &str) -> Result<(), CommandError> {
    host.apply(Command::SetServer {
        host: name.into(),
        port: 4303,
        bus: 2,
    })
}

#[test]
fn the_server_defaults_to_electrip_1() {
    let (host, _, _) = host();
    let station = host.session().station();
    assert_eq!(
        (station.host.as_str(), station.port, station.bus),
        ("localhost", 4303, 1)
    );
    assert!(!station.connected);
}

#[test]
fn connects_to_the_configured_server() {
    let (mut host, _, _) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    let station = host.session().station();
    assert_eq!((station.host.as_str(), station.bus), ("srcp", 2));
    assert!(station.connected);
}

#[test]
fn a_failed_connect_reports_the_error_and_changes_nothing() {
    let (mut host, _, _) = host();
    let before = host.session().clone();
    let error = host.apply(Command::Connect).unwrap_err();
    assert_eq!(error.to_string(), "cannot reach localhost");
    assert_eq!(*host.session(), before);
}

#[test]
fn the_server_changes_only_while_disconnected() {
    let (mut host, _, _) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    assert_eq!(set_server(&mut host, "other"), Err(CommandError::Connected));
    host.apply(Command::Disconnect).unwrap();
    assert!(!host.session().station().connected);
    set_server(&mut host, "other").unwrap();
}

#[test]
fn a_broken_connection_disconnects_and_can_be_reopened() {
    let (mut host, events, _) = host();
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
fn driving_host() -> (Host, Sent) {
    let (mut host, _, sent) = host();
    host.apply(Command::AddLoco).unwrap();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    sent.lock().unwrap().clear();
    (host, sent)
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
    let (mut host, sent) = driving_host();
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
    let (mut host, sent) = driving_host();
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
    let (mut host, _) = driving_host();
    set_axis(&mut host, 1.0);
    host.poll(11.5);
    set_axis(&mut host, -0.5);
    host.poll(8.5);
    assert!((speed(&host) - 50.0).abs() < 1e-9);
}

#[test]
fn reverse_stops_and_changes_the_direction() {
    let (mut host, sent) = driving_host();
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
    let (mut host, _, _) = host();
    host.apply(Command::AddLoco).unwrap();
    set_axis(&mut host, 1.0);
    assert!(host.poll(11.5));
    assert_eq!(speed(&host), 100.0);
}

#[test]
fn the_axis_of_an_unknown_loco_is_an_error() {
    let (mut host, _, _) = host();
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
    let (mut host, _, sent) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    assert!(host.session().station().track_power);
    assert_eq!(*sent.lock().unwrap(), [Call::Power(true)]);
    host.apply(Command::Disconnect).unwrap();
    assert!(!host.session().station().track_power);
}

#[test]
fn connecting_leaves_the_track_power_if_switched_off() {
    let (mut host, _, sent) = host();
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
    let (mut host, sent) = driving_host();
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
    let (mut host, _, _) = host();
    let error = host.apply(Command::TogglePower);
    assert_eq!(error, Err(CommandError::Disconnected));
}

#[test]
fn the_track_power_follows_the_command_station() {
    let (mut host, events, _) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    events.lock().unwrap().push(StationEvent::Power(false));
    assert!(host.poll(0.05));
    assert!(!host.session().station().track_power);
}

#[test]
fn the_loco_emergency_stop_stops_only_the_loco() {
    let (mut host, sent) = driving_host();
    set_axis(&mut host, 1.0);
    host.poll(11.5);
    sent.lock().unwrap().clear();
    host.apply(Command::EmergencyStop { loco: 1 }).unwrap();
    host.poll(1.0);
    assert_eq!(speed(&host), 0.0);
    assert!(host.session().station().track_power);
    assert_eq!(*sent.lock().unwrap(), [Call::EmergencyStop(1)]);
}
