use super::*;
use electrip_core::audio::{AudioSink, ChannelId};
use electrip_core::station::StationError;
use std::net::SocketAddr;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tempfile::TempDir;

struct NoAudio;

impl AudioSink for NoAudio {
    fn length(&mut self, _: &Path) -> Result<Duration, String> {
        Err("no audio".into())
    }

    fn queue(&mut self, _: ChannelId, _: &Path) {}

    fn play(&mut self, _: ChannelId, _: &Path, _: Duration) {}

    fn stop(&mut self, _: ChannelId) {}

    fn fade_in(&mut self, _: ChannelId, _: &Path, _: Duration) {}

    fn fade_out(&mut self, _: ChannelId, _: Duration) {}
}

/// A relay to `host` for an instance without sound.
fn relay(host: SocketAddr) -> Relay {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    Relay::start(listener, host, 2, Box::new(NoAudio))
}

/// A host without sound and its library, deleted when dropped.
fn host() -> (Host, TempDir) {
    host_in(TempDir::new().unwrap())
}

fn host_in(library: TempDir) -> (Host, TempDir) {
    let connect = Box::new(|_: &_| Err(StationError("no station".into())));
    let host = Host::new(connect, Box::new(NoAudio), library.path().into()).unwrap();
    (host, library)
}

#[test]
fn execute_applies_a_command() {
    let (mut host, _library) = host();
    assert_eq!(
        execute(&mut host, r#"{"command": "add_loco"}"#),
        Ok(Command::AddLoco)
    );
    assert_eq!(host.session().locos().len(), 1);
}

#[test]
fn execute_explains_invalid_json() {
    let (mut host, _library) = host();
    let error = execute(&mut host, r#"{"command": "fly"}"#).unwrap_err();
    assert!(
        error.starts_with("invalid command: unknown variant `fly`"),
        "{error}"
    );
}

#[test]
fn execute_explains_a_failed_command() {
    let (mut host, _library) = host();
    let error = execute(
        &mut host,
        r#"{"command": "set_address", "loco": 1, "address": 3}"#,
    );
    assert_eq!(error, Err("there is no loco with id 1".into()));
}

#[test]
fn replies_report_success_or_the_error() {
    assert_eq!(
        reply(&Ok(Command::AddLoco)),
        json!({"type": "reply", "ok": true})
    );
    assert_eq!(
        reply::<Command>(&Err("oops".into())),
        json!({"type": "reply", "ok": false, "error": "oops"})
    );
}

#[test]
fn hello_tells_why_the_instance_runs_alone() {
    assert_eq!(
        hello("7", None),
        json!({"type": "hello", "version": VERSION, "id": "7"})
    );
    assert_eq!(
        hello("7", Some("no access to the local network")),
        json!({"type": "hello", "version": VERSION, "id": "7", "alone": "no access to the local network"})
    );
}

/// Serves a new host on a free port; returns its address.
fn serve_host() -> (SocketAddr, TempDir) {
    serve_library(TempDir::new().unwrap())
}

/// Serves a new host on `library`.
pub(crate) fn serve_library(library: TempDir) -> (SocketAddr, TempDir) {
    let (host, library) = host_in(library);
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    thread::spawn(move || serve(listener, host, 1, Vec::new, None, || None));
    (address, library)
}

/// Input that adds gamepad 1 once.
fn one_gamepad() -> impl FnMut() -> Vec<Command> {
    let mut added = false;
    move || {
        let kind = "Gamepad".to_string();
        let commands = if added {
            vec![]
        } else {
            vec![Command::AddDevice { device: 1, kind }]
        };
        added = true;
        commands
    }
}

/// The id of the first input device the host at `address` reports.
fn first_device(address: SocketAddr) -> u64 {
    let stream = TcpStream::connect(address).unwrap();
    BufReader::new(stream)
        .lines()
        .map(|line| serde_json::from_str::<Value>(&line.unwrap()).unwrap())
        .find_map(|message| message["state"]["devices"][0]["id"].as_u64())
        .unwrap()
}

#[test]
fn a_client_instance_sends_its_devices_to_the_host() {
    let (address, _library) = serve_host();
    let mut relay = relay(address);
    thread::spawn(move || relay.run(one_gamepad()));

    let id = first_device(address);
    // Offset, so gamepads of different instances keep apart.
    assert_ne!(id, 1);
    assert_eq!(id & 0xffff, 1);
}

#[test]
fn the_host_sends_a_sign_of_life_each_second() {
    let (address, _library) = serve_host();
    let stream = TcpStream::connect(address).unwrap();
    stream.set_read_timeout(Some(SILENCE)).unwrap();
    let mut lines = BufReader::new(stream).lines();
    lines.next(); // hello
    lines.next(); // state
    let start = Instant::now();
    let state: Value = serde_json::from_str(&lines.next().unwrap().unwrap()).unwrap();
    assert_eq!(state["type"], "state");
    assert!(start.elapsed() < Duration::from_millis(1500));
}

#[test]
fn a_silent_host_counts_as_gone() {
    let silent = TcpListener::bind("127.0.0.1:0").unwrap();
    let mut relay = relay(silent.local_addr().unwrap());
    let start = Instant::now();
    assert!(relay.run(Vec::new).is_err());
    let took = start.elapsed();
    assert!(took >= SILENCE && took < SILENCE * 2, "{took:?}");
}

#[test]
fn the_next_host_gets_the_devices_still_connected() {
    let gone = TcpListener::bind("127.0.0.1:0").unwrap();
    let mut relay = relay(gone.local_addr().unwrap());
    // The host closes the connection after the offer and the first
    // command.
    thread::spawn(move || {
        let (stream, _) = gone.accept().unwrap();
        BufReader::new(stream).lines().nth(1);
    });
    let mut input = one_gamepad();
    assert!(relay.run(&mut input).is_err());

    let (address, _library) = serve_host();
    relay.switch(address, true);
    thread::spawn(move || relay.run(input));
    assert_eq!(first_device(address) & 0xffff, 1);
}

#[test]
fn a_host_that_hands_over_closes_all_connections() {
    let (host, _library) = host();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let next: SocketAddr = "192.168.1.7:4711".parse().unwrap();
    let (sender, receiver) = std::sync::mpsc::channel();
    let server = thread::spawn(move || {
        serve(listener, host, 1, Vec::new, None, || {
            receiver.try_recv().ok()
        })
    });
    let stream = TcpStream::connect(address).unwrap();
    stream.set_read_timeout(Some(SILENCE)).unwrap();
    let mut lines = BufReader::new(stream).lines();
    lines.next(); // hello

    sender.send(next).unwrap();
    assert_eq!(server.join().unwrap().unwrap(), next);
    // The rest of the messages, then the end of the connection.
    assert!(lines.all(|line| line.is_ok()));
    // No client gets in any more.
    let late = TcpStream::connect(address).map(|stream| BufReader::new(stream).lines().next());
    assert!(!matches!(late, Ok(Some(Ok(_)))), "{late:?}");
}

/// Sends a `join_host` request to the host at `host`; returns the reply.
fn ask_to_join(host: SocketAddr, address: &str) -> Value {
    request(host, json!({"command": "join_host", "address": address}))
}

/// Sends `request` to the host at `host`; returns the reply.
pub(crate) fn request(host: SocketAddr, request: Value) -> Value {
    let mut stream = TcpStream::connect(host).unwrap();
    send(&mut stream, &request).unwrap();
    BufReader::new(stream)
        .lines()
        .map(|line| serde_json::from_str::<Value>(&line.unwrap()).unwrap())
        .find(|message| message["type"] == "reply")
        .unwrap()
}

#[test]
fn a_host_joins_the_host_a_client_names() {
    let (next, _next_library) = serve_host();
    let (host, _library) = host();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let server = thread::spawn(move || serve(listener, host, 2, Vec::new, None, || None));

    let reply = ask_to_join(address, &next.to_string());
    assert_eq!(reply, json!({"type": "reply", "ok": true}));
    assert_eq!(server.join().unwrap().unwrap(), next);
}

#[test]
fn a_host_does_not_join_itself_or_an_unreachable_host() {
    let (address, _library) = serve_host();
    let reply = ask_to_join(address, &address.to_string());
    assert_eq!(
        reply["error"],
        format!("{address} is already in this session")
    );

    let reply = ask_to_join(address, "127.0.0.1:1");
    let error = reply["error"].as_str().unwrap();
    assert!(
        error.starts_with("cannot reach the host 127.0.0.1:1: "),
        "{error}"
    );
    // Still the host.
    assert_eq!(ask_to_join(address, "")["ok"], false);
}

#[test]
fn a_join_request_names_the_host() {
    assert_eq!(
        join_request(r#"{"command": "join_host", "address": "pc:4711"}"#),
        Some("pc:4711".into())
    );
    assert_eq!(join_request(r#"{"command": "add_loco"}"#), None);
}

#[test]
fn an_instance_keeps_its_id_in_the_library() {
    let (a, b) = (TempDir::new().unwrap(), TempDir::new().unwrap());
    let id = instance_id(a.path()).unwrap();
    assert_eq!(instance_id(a.path()).unwrap(), id);
    assert_ne!(instance_id(b.path()).unwrap(), id);
}

/// Reads messages until the first one `found` accepts.
fn wait_for(lines: &mut impl Iterator<Item = io::Result<String>>, found: impl Fn(&Value) -> bool) {
    lines
        .map(|line| serde_json::from_str::<Value>(&line.unwrap()).unwrap())
        .find(found)
        .unwrap();
}

#[test]
fn the_host_sends_the_sounds_of_a_loco_to_its_instance_while_connected() {
    let (address, _library) = serve_host();
    let mut client = TcpStream::connect(address).unwrap();
    client.set_read_timeout(Some(SILENCE)).unwrap();
    let mut lines = BufReader::new(client.try_clone().unwrap()).lines();
    let offer = json!({"command": "offer_audio", "instance": "b", "devices": ["USB"]});
    send(&mut client, &offer).unwrap();
    wait_for(&mut lines, |m| {
        m["state"]["audio_targets"] == json!({"b": ["USB"]})
    });

    send(&mut client, &json!({"command": "add_loco"})).unwrap();
    let target =
        json!({"command": "set_audio_device", "loco": 1, "instance": "b", "device": "USB"});
    send(&mut client, &target).unwrap();
    let route = json!({"event": "route", "loco": 1, "device": "USB"});
    wait_for(&mut lines, |m| m["type"] == "audio" && m["audio"] == route);

    drop((lines, client));
    let mut lines = BufReader::new(TcpStream::connect(address).unwrap()).lines();
    wait_for(&mut lines, |m| m["state"]["audio_targets"] == json!({}));
}

/// An audio target that logs the devices of the locos.
#[derive(Default, Clone)]
struct Routes(Arc<Mutex<Vec<String>>>);

impl AudioSink for Routes {
    fn length(&mut self, _: &Path) -> Result<Duration, String> {
        Err("no audio".into())
    }

    fn queue(&mut self, _: ChannelId, _: &Path) {}

    fn play(&mut self, _: ChannelId, _: &Path, _: Duration) {}

    fn stop(&mut self, _: ChannelId) {}

    fn fade_in(&mut self, _: ChannelId, _: &Path, _: Duration) {}

    fn fade_out(&mut self, _: ChannelId, _: Duration) {}

    fn devices(&mut self) -> Vec<String> {
        vec!["USB".into()]
    }

    fn route(&mut self, loco: u32, device: Option<&str>) {
        self.0.lock().unwrap().push(format!("{loco} {device:?}"));
    }
}

#[test]
fn a_client_instance_offers_its_audio_target_and_plays_the_audio_events() {
    let host = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = host.local_addr().unwrap();
    let routes = Routes::default();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let mut relay = Relay::start(listener, address, 0xb, Box::new(routes.clone()));
    thread::spawn(move || relay.run(Vec::new));

    let (mut stream, _) = host.accept().unwrap();
    let mut lines = BufReader::new(stream.try_clone().unwrap()).lines();
    let offer: Value = serde_json::from_str(&lines.next().unwrap().unwrap()).unwrap();
    let expected =
        json!({"command": "offer_audio", "instance": "000000000000000b", "devices": ["USB"]});
    assert_eq!(offer, expected);
    let route = json!({"event": "route", "loco": 3, "device": "USB"});
    send(&mut stream, &json!({"type": "audio", "audio": route})).unwrap();
    let start = Instant::now();
    while routes.0.lock().unwrap().is_empty() && start.elapsed() < SILENCE {
        thread::sleep(Duration::from_millis(10));
    }
    assert_eq!(*routes.0.lock().unwrap(), [r#"3 Some("USB")"#]);

    send(&mut stream, &json!({"type": "ping"})).unwrap();
    let pong: Value = serde_json::from_str(&lines.next().unwrap().unwrap()).unwrap();
    assert_eq!(pong, json!({"command": "pong"}));
}

#[test]
fn an_instance_that_reconnects_keeps_its_audio_target() {
    let (address, _library) = serve_host();
    let offer = json!({"command": "offer_audio", "instance": "b", "devices": []});
    let reply = |m: &Value| m["type"] == "reply";
    let mut old = TcpStream::connect(address).unwrap();
    send(&mut old, &offer).unwrap();
    wait_for(&mut BufReader::new(old.try_clone().unwrap()).lines(), reply);
    let mut new = TcpStream::connect(address).unwrap();
    send(&mut new, &offer).unwrap();
    wait_for(&mut BufReader::new(new.try_clone().unwrap()).lines(), reply);

    drop(old);
    thread::sleep(Duration::from_millis(200));
    let mut at_host = BufReader::new(TcpStream::connect(address).unwrap()).lines();
    at_host.next(); // hello
    let state: Value = serde_json::from_str(&at_host.next().unwrap().unwrap()).unwrap();
    assert_eq!(state["state"]["audio_targets"], json!({"b": []}));
}

#[test]
fn the_host_measures_the_round_trip_to_an_audio_target() {
    let (address, _library) = serve_host();
    let mut client = TcpStream::connect(address).unwrap();
    client.set_read_timeout(Some(SILENCE)).unwrap();
    let mut lines = BufReader::new(client.try_clone().unwrap()).lines();
    let offer = json!({"command": "offer_audio", "instance": "b", "devices": []});
    send(&mut client, &offer).unwrap();
    wait_for(&mut lines, |m| m["type"] == "ping");
    thread::sleep(Duration::from_millis(120));
    send(&mut client, &json!({"command": "pong"})).unwrap();
    let latency = |m: &Value| m["state"]["audio_latency"]["b"].as_u64();
    wait_for(&mut lines, |m| {
        latency(m).is_some_and(|l| (120..300).contains(&l))
    });
    // The next ping a heartbeat later.
    wait_for(&mut lines, |m| m["type"] == "ping");

    drop((lines, client));
    let mut lines = BufReader::new(TcpStream::connect(address).unwrap()).lines();
    wait_for(&mut lines, |m| m["state"]["audio_latency"] == json!({}));
}
