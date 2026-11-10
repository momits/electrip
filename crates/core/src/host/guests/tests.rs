use super::*;
use crate::decoder::{Decoder, Protocol};
use crate::host::tests::{Call, driving_host, host_with_light, report, set_axis, speed, state};
use crate::loco::Loco;
use crate::session::LocoEntry;

/// A configuration "guest" with a loco at address 1 that reaches only
/// 50 km/h and one at address 2.
fn guest_config() -> Config {
    let loco = |address| {
        Loco::new(
            Decoder::new(Protocol::DccShort, address, 128).unwrap(),
            50.0,
        )
    };
    Config {
        id: "guest".into(),
        locos: vec![loco(1).unwrap(), loco(2).unwrap()],
        ..Config::default()
    }
}

fn guest_loco(host: &Host) -> &LocoEntry {
    &host.guest("guest").unwrap().locos()[0]
}

fn guest_axis(host: &mut Host, deflection: f64) {
    let loco = guest_loco(host).id;
    host.apply_guest("guest", Command::SetAxis { loco, deflection })
        .unwrap();
}

#[test]
fn loco_ids_stay_unique_on_the_host() {
    let (mut host, _, _library) = driving_host();
    host.add_guest(guest_config());
    host.apply(Command::AddLoco).unwrap();
    let guest = host.guest("guest").unwrap().locos();
    let ids: Vec<u32> = host.session().locos().iter().map(|e| e.id).collect();
    assert_eq!((guest[0].id, guest[1].id), (2, 3));
    assert_eq!(ids, [1, 4]);
}

#[test]
fn the_guest_takes_over_what_the_host_drives() {
    let (mut host, sent, _library) = driving_host();
    host.add_guest(guest_config());
    set_axis(&mut host, 1.0);
    host.poll(1.15);
    assert_eq!(guest_loco(&host).station_state().step, 12);
    let calls = sent.lock().unwrap();
    let locos: Vec<&Call> = calls
        .iter()
        .filter(|c| matches!(c, Call::Loco(..)))
        .collect();
    assert_eq!(locos, [&state(true, 12)]);
}

#[test]
fn the_host_takes_over_what_the_guest_drives_with_its_speed_curve() {
    let (mut host, sent, _library) = driving_host();
    host.add_guest(guest_config());
    host.poll(0.05);
    guest_axis(&mut host, 1.0);
    host.poll(20.0);
    assert_eq!(guest_loco(&host).motion.speed(), 50.0);
    assert_eq!(speed(&host), 100.0);
    assert!(sent.lock().unwrap().contains(&state(true, 128)));
}

#[test]
fn the_last_deflected_axis_wins() {
    let (mut host, _, _library) = driving_host();
    host.add_guest(guest_config());
    set_axis(&mut host, 1.0);
    host.poll(5.75);
    guest_axis(&mut host, -1.0);
    for _ in 0..100 {
        host.poll(0.05);
    }
    assert_eq!((speed(&host), guest_loco(&host).motion.speed()), (0.0, 0.0));
}

#[test]
fn a_new_guest_takes_over_the_state_without_sending() {
    let (mut host, sent, _library) = driving_host();
    set_axis(&mut host, 1.0);
    host.poll(11.5);
    sent.lock().unwrap().clear();
    host.add_guest(guest_config());
    host.poll(0.05);
    assert_eq!(guest_loco(&host).motion.speed(), 50.0);
    assert_eq!(*sent.lock().unwrap(), [Call::Request(1), Call::Request(2)]);
}

#[test]
fn the_guest_takes_over_a_change_by_another_program() {
    let (mut host, events, _, _library) = host_with_light();
    host.add_guest(guest_config());
    report(&events, false, 64, 0);
    host.poll(0.05);
    let state = guest_loco(&host).station_state();
    assert_eq!((state.forward, state.step), (false, 64));
}

#[test]
fn a_guest_only_drives() {
    let (mut host, _, _library) = driving_host();
    host.add_guest(guest_config());
    let loco = guest_loco(&host).id;
    let rename = Command::RenameLoco {
        loco,
        name: "V 60".into(),
    };
    let error = host.apply_guest("guest", rename).unwrap_err();
    assert_eq!(error, CommandError::GuestChange);
    host.apply_guest("guest", Command::Reverse { loco })
        .unwrap();
    assert!(!guest_loco(&host).motion.forward());
}

#[test]
fn the_configuration_of_the_host_is_no_guest() {
    let (mut host, _, _library) = driving_host();
    let config = host.session().config();
    host.add_guest(config.clone());
    assert!(host.guest(&config.id).is_none());
    let error = host.apply_guest("other", Command::AddLoco).unwrap_err();
    assert_eq!(
        error.to_string(),
        "the configuration other is not in this session"
    );
}

#[test]
fn a_removed_guest_is_gone() {
    let (mut host, _, _library) = driving_host();
    host.add_guest(guest_config());
    host.remove_guest("guest");
    assert!(host.guest("guest").is_none());
}

#[test]
fn an_emergency_stop_by_the_guest_stops_what_the_host_drives() {
    let (mut host, _, _library) = driving_host();
    host.add_guest(guest_config());
    set_axis(&mut host, 1.0);
    host.poll(5.75);
    let loco = guest_loco(&host).id;
    host.apply_guest("guest", Command::EmergencyStop { loco })
        .unwrap();
    host.poll(1.0);
    assert_eq!((speed(&host), guest_loco(&host).motion.speed()), (0.0, 0.0));
}

#[test]
fn a_guest_sees_the_command_station_and_audio_targets_of_the_host() {
    let (mut host, _, _library) = driving_host();
    host.add_guest(guest_config());
    host.apply(Command::TogglePower).unwrap();
    host.add_audio_target("b".into(), vec!["USB".into()], Box::new(|_| true));
    host.set_audio_latency("b", std::time::Duration::from_millis(30));

    let view = host.guest_view("guest").unwrap();
    assert_eq!(view.station(), host.session().station());
    assert!(view.station().connected);
    let state = serde_json::to_value(&view).unwrap();
    assert_eq!(state["audio_targets"], serde_json::json!({"b": ["USB"]}));
    assert_eq!(state["audio_latency"], serde_json::json!({"b": 30}));
    assert_eq!(view.locos(), host.guest("guest").unwrap().locos());
}

#[test]
fn the_host_and_the_guest_learn_of_an_address_with_two_audio_targets() {
    let (mut host, _, _library) = driving_host();
    let mut config = guest_config();
    config.locos[0].set_audio_target(Some("b".into()), None);
    host.add_guest(config);
    assert!(host.poll(0.05));
    assert!(!host.poll(0.05));

    let conflicts =
        |session: &Session| serde_json::to_value(session).unwrap()["audio_conflicts"].clone();
    assert_eq!(conflicts(host.session()), serde_json::json!([1]));
    assert_eq!(
        conflicts(&host.guest_view("guest").unwrap()),
        serde_json::json!([1])
    );
    host.apply(Command::SetAudioDevice {
        loco: 1,
        instance: Some("b".into()),
        device: None,
    })
    .unwrap();
    assert!(host.poll(0.05));
    assert_eq!(conflicts(host.session()), serde_json::json!([]));
}
