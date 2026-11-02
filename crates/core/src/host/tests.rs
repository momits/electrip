use super::*;
use crate::decoder::Decoder;
use crate::station::LocoState;
use std::sync::{Arc, Mutex};

/// Events the test hands to the fake driver.
type Events = Arc<Mutex<Vec<StationEvent>>>;

struct FakeDriver(Events);

impl CommandStation for FakeDriver {
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
        std::mem::take(&mut self.0.lock().unwrap())
    }
}

/// A host whose connector reaches only the server "srcp", and its events.
fn host() -> (Host, Events) {
    let events = Events::default();
    let driver_events = Arc::clone(&events);
    let host = Host::new(Box::new(move |station| {
        if station.host == "srcp" {
            Ok(Box::new(FakeDriver(Arc::clone(&driver_events))))
        } else {
            Err(StationError(format!("cannot reach {}", station.host)))
        }
    }));
    (host, events)
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
    let (host, _) = host();
    let station = host.session().station();
    assert_eq!(
        (station.host.as_str(), station.port, station.bus),
        ("localhost", 4303, 1)
    );
    assert!(!station.connected);
}

#[test]
fn connects_to_the_configured_server() {
    let (mut host, _) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    let station = host.session().station();
    assert_eq!((station.host.as_str(), station.bus), ("srcp", 2));
    assert!(station.connected);
}

#[test]
fn a_failed_connect_reports_the_error_and_changes_nothing() {
    let (mut host, _) = host();
    let before = host.session().clone();
    let error = host.apply(Command::Connect).unwrap_err();
    assert_eq!(error.to_string(), "cannot reach localhost");
    assert_eq!(*host.session(), before);
}

#[test]
fn the_server_changes_only_while_disconnected() {
    let (mut host, _) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    assert_eq!(set_server(&mut host, "other"), Err(CommandError::Connected));
    host.apply(Command::Disconnect).unwrap();
    assert!(!host.session().station().connected);
    set_server(&mut host, "other").unwrap();
}

#[test]
fn a_broken_connection_disconnects_and_can_be_reopened() {
    let (mut host, events) = host();
    set_server(&mut host, "srcp").unwrap();
    host.apply(Command::Connect).unwrap();
    assert!(!host.poll());
    events.lock().unwrap().push(StationEvent::Disconnected);
    assert!(host.poll());
    assert!(!host.session().station().connected);
    host.apply(Command::Connect).unwrap();
    assert!(host.session().station().connected);
}
