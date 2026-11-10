use super::*;
use electrip_core::audio::{AudioSink, ChannelId};
use electrip_core::station::StationError;
use std::net::SocketAddr;
use std::path::Path;
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

/// A host without sound and its library, deleted when dropped.
fn host() -> (Host, TempDir) {
    let library = TempDir::new().unwrap();
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
        reply(&Err("oops".into())),
        json!({"type": "reply", "ok": false, "error": "oops"})
    );
}

#[test]
fn hello_tells_why_the_instance_runs_alone() {
    assert_eq!(hello(None), json!({"type": "hello", "version": VERSION}));
    assert_eq!(
        hello(Some("no access to the local network")),
        json!({"type": "hello", "version": VERSION, "alone": "no access to the local network"})
    );
}

/// Serves a new host on a free port; returns its address.
fn serve_host() -> (SocketAddr, TempDir) {
    let (host, library) = host();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    thread::spawn(move || serve(listener, host, Vec::new, None));
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
    let mut relay = Relay::start(TcpListener::bind("127.0.0.1:0").unwrap(), address);
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
    let mut relay = Relay::start(
        TcpListener::bind("127.0.0.1:0").unwrap(),
        silent.local_addr().unwrap(),
    );
    let start = Instant::now();
    assert!(relay.run(Vec::new).is_err());
    let took = start.elapsed();
    assert!(took >= SILENCE && took < SILENCE * 2, "{took:?}");
}

#[test]
fn the_next_host_gets_the_devices_still_connected() {
    let gone = TcpListener::bind("127.0.0.1:0").unwrap();
    let mut relay = Relay::start(
        TcpListener::bind("127.0.0.1:0").unwrap(),
        gone.local_addr().unwrap(),
    );
    // The host closes the connection after the first command.
    thread::spawn(move || {
        let (stream, _) = gone.accept().unwrap();
        BufReader::new(stream).lines().next();
    });
    let mut input = one_gamepad();
    assert!(relay.run(&mut input).is_err());

    let (address, _library) = serve_host();
    relay.switch(address);
    thread::spawn(move || relay.run(input));
    assert_eq!(first_device(address) & 0xffff, 1);
}
