use super::*;
use electrip_core::audio::{AudioSink, ChannelId};
use electrip_core::station::StationError;
use std::path::Path;
use std::time::Duration;
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
fn a_client_instance_sends_its_devices_to_the_host() {
    let (host, _library) = host();
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    thread::spawn(move || serve(listener, host, Vec::new));
    let mut added = false;
    let input = move || {
        let kind = "Gamepad".to_string();
        let commands = if added {
            vec![]
        } else {
            vec![Command::AddDevice { device: 1, kind }]
        };
        added = true;
        commands
    };
    let relayed = TcpListener::bind("127.0.0.1:0").unwrap();
    thread::spawn(move || relay(relayed, address, input));

    let stream = TcpStream::connect(address).unwrap();
    let id = BufReader::new(stream)
        .lines()
        .map(|line| serde_json::from_str::<Value>(&line.unwrap()).unwrap())
        .find_map(|message| message["state"]["devices"][0]["id"].as_u64());
    // Offset, so gamepads of different instances keep apart.
    let id = id.unwrap();
    assert_ne!(id, 1);
    assert_eq!(id & 0xffff, 1);
}
