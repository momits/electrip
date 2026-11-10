use super::*;
use crate::audio::tests::LogSink;
use std::sync::{Arc, Mutex};

type Sent = Arc<Mutex<Vec<AudioEvent>>>;

/// Targets on the host's `LogSink` and an instance "b" that logs what it
/// gets while `alive`.
fn targets(alive: bool) -> (Targets, LogSink, Sent) {
    let local = LogSink::new(&[("a.ogg", 1.0)]);
    let log = LogSink {
        played: Arc::clone(&local.played),
        routes: Arc::clone(&local.routes),
        prepared: Arc::clone(&local.prepared),
        ..LogSink::default()
    };
    let mut targets = Targets::new(Box::new(local));
    let sent = Sent::default();
    let remote = Arc::clone(&sent);
    targets.add(
        "b".into(),
        Box::new(move |event| {
            remote.lock().unwrap().push(event.clone());
            alive
        }),
    );
    (targets, log, sent)
}

fn channel(loco: u32) -> ChannelId {
    ChannelId { loco, nr: 0 }
}

fn queue(channel: ChannelId) -> AudioEvent {
    let sound = "a.ogg".into();
    AudioEvent::Queue { channel, sound }
}

#[test]
fn each_loco_plays_on_its_instance() {
    let (mut targets, host, sent) = targets(true);
    targets.route(1, None, None);
    targets.route(2, Some("b"), Some("USB"));
    targets.queue(channel(1), Path::new("a.ogg"));
    targets.queue(channel(2), Path::new("a.ogg"));
    assert_eq!(host.take(), ["1 a.ogg"]);
    let route = AudioEvent::Route {
        loco: 2,
        device: Some("USB".into()),
    };
    assert_eq!(*sent.lock().unwrap(), [route, queue(channel(2))]);
    assert_eq!(
        targets.length(Path::new("a.ogg")),
        Ok(Duration::from_secs(1))
    );
}

#[test]
fn the_host_plays_for_an_instance_that_is_not_connected() {
    let (mut targets, host, sent) = targets(true);
    targets.route(1, Some("c"), Some("USB"));
    targets.queue(channel(1), Path::new("a.ogg"));
    assert_eq!(host.take(), ["1 a.ogg"]);
    assert_eq!(host.routes.lock().unwrap()[&1], None);
    assert!(sent.lock().unwrap().is_empty());
}

#[test]
fn the_host_plays_for_an_instance_that_is_gone() {
    let (mut targets, host, _sent) = targets(false);
    targets.route(1, Some("b"), None);
    targets.queue(channel(1), Path::new("a.ogg"));
    assert_eq!(host.take(), ["1 a.ogg"]);
}

#[test]
fn a_loco_that_moves_falls_silent_on_the_old_instance() {
    let (mut targets, host, sent) = targets(true);
    targets.route(1, Some("b"), None);
    targets.queue(channel(1), Path::new("a.ogg"));
    sent.lock().unwrap().clear();

    targets.route(1, None, None);
    let stop = AudioEvent::Stop {
        channel: channel(1),
    };
    assert_eq!(*sent.lock().unwrap(), [stop]);
    targets.queue(channel(1), Path::new("a.ogg"));
    assert_eq!(host.take(), ["1 a.ogg"]);
}

#[test]
fn a_loco_that_is_gone_falls_silent() {
    let (mut targets, host, sent) = targets(true);
    targets.route(1, None, None);
    targets.route(2, Some("b"), None);
    targets.queue(channel(1), Path::new("a.ogg"));
    targets.queue(channel(2), Path::new("a.ogg"));
    host.take();
    sent.lock().unwrap().clear();

    targets.retain(&HashSet::from([2]));
    assert_eq!(host.take(), ["1 stop"]);
    targets.retain(&HashSet::new());
    let stop = AudioEvent::Stop {
        channel: channel(2),
    };
    assert_eq!(*sent.lock().unwrap(), [stop]);
    targets.retain(&HashSet::new());
    assert!(host.take().is_empty());
}

#[test]
fn an_unchanged_route_is_not_sent_again() {
    let (mut targets, _host, sent) = targets(true);
    targets.route(1, Some("b"), None);
    targets.route(1, Some("b"), None);
    assert_eq!(sent.lock().unwrap().len(), 1);
}

#[test]
fn the_instance_of_a_loco_reads_its_sounds_ahead_once() {
    let (mut targets, host, sent) = targets(true);
    targets.route(1, None, None);
    targets.route(2, Some("b"), None);
    sent.lock().unwrap().clear();
    for _ in 0..2 {
        targets.read_ahead(1, Path::new("a.ogg"));
        targets.read_ahead(2, Path::new("b.ogg"));
    }
    let prepare = AudioEvent::Prepare {
        sound: "b.ogg".into(),
    };
    assert_eq!(*sent.lock().unwrap(), std::slice::from_ref(&prepare));
    assert!(host.prepared.lock().unwrap().contains(&"b.ogg".into()));

    let again = Sent::default();
    let remote = Arc::clone(&again);
    targets.add(
        "b".into(),
        Box::new(move |event| {
            remote.lock().unwrap().push(event.clone());
            true
        }),
    );
    targets.read_ahead(2, Path::new("b.ogg"));
    assert_eq!(*again.lock().unwrap(), [prepare]);
}

#[test]
fn an_event_reads_back_from_json() {
    let event = AudioEvent::Play {
        channel: channel(3),
        sound: "sounds/x.ogg".into(),
        delay: Duration::from_millis(250),
    };
    let json = serde_json::to_string(&event).unwrap();
    assert_eq!(serde_json::from_str::<AudioEvent>(&json).unwrap(), event);
}
