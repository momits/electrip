use super::*;

#[test]
fn parses_power() {
    let line = "1793623957.766 100 INFO 1 POWER OFF";
    assert_eq!(parse_info(line, 1), Some(StationEvent::Power(false)));
}

#[test]
fn parses_loco_with_functions() {
    let functions = "1 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1";
    let line = format!("1793623970.454 100 INFO 1 GL 8 1 7 28 {functions}");
    let state = LocoState {
        forward: true,
        step: 7,
        functions: 1 | 1 << 2 | 1 << 28,
    };
    let event = StationEvent::Loco { address: 8, state };
    assert_eq!(parse_info(&line, 1), Some(event));
}

#[test]
fn parses_backward_loco_without_functions() {
    let line = "1793623970.454 100 INFO 1 GL 3 0 0 14";
    let event = StationEvent::Loco {
        address: 3,
        state: LocoState::default(),
    };
    assert_eq!(parse_info(line, 1), Some(event));
}

#[test]
fn ignores_other_buses_and_messages() {
    assert_eq!(parse_info("1.0 100 INFO 2 POWER ON", 1), None);
    assert_eq!(parse_info("1.0 101 INFO 1 GL 3 N 1 128 29", 1), None);
    assert_eq!(parse_info("1.0 100 INFO 1 DESCRIPTION GA GL FB", 1), None);
    assert_eq!(parse_info("1.0 100 INFO 0 SESSION 6 COMMAND", 1), None);
}

/// A server that accepts the handshake of a COMMAND and an INFO session,
/// then closes the INFO session.
fn closing_server() -> u16 {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    thread::spawn(move || {
        let mut sessions = Vec::new();
        for replies in [3, 2] {
            let (stream, _) = listener.accept().unwrap();
            let mut session = BufReader::new(stream);
            writeln!(session.get_mut(), "srcpd V2.1.7; SRCP 0.8.4").unwrap();
            for _ in 0..replies {
                read_line(&mut session).unwrap();
                writeln!(session.get_mut(), "1.0 200 OK").unwrap();
            }
            sessions.push(session);
        }
        drop(sessions.pop());
        thread::sleep(Duration::from_secs(5));
    });
    port
}

#[test]
fn reports_a_broken_connection() {
    let station = SrcpStation::connect("127.0.0.1", closing_server(), 1).unwrap();
    let event = station.events.recv_timeout(Duration::from_secs(5));
    assert_eq!(event, Ok(StationEvent::Disconnected));
}
