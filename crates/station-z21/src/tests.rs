use super::*;

#[test]
fn reports_when_no_z21_answers() {
    let unused = UdpSocket::bind("127.0.0.1:0").unwrap();
    let port = unused.local_addr().unwrap().port();
    drop(unused);
    let error = Z21Station::connect("127.0.0.1", port).err().unwrap();
    assert!(
        error
            .0
            .starts_with(&format!("no Z21 answers on 127.0.0.1:{port}: ")),
        "{error}"
    );
    let error = Z21Station::connect("no-such-host.invalid", DEFAULT_PORT)
        .err()
        .unwrap();
    assert!(
        error
            .0
            .starts_with("cannot reach the Z21 no-such-host.invalid:21105: "),
        "{error}"
    );
}

#[test]
fn reports_a_z21_that_goes_away() {
    let z21 = UdpSocket::bind("127.0.0.1:0").unwrap();
    let port = z21.local_addr().unwrap().port();
    let answer = std::thread::spawn(move || {
        let mut buffer = [0; 100];
        let (_, client) = z21.recv_from(&mut buffer).unwrap();
        // LAN_X_STATUS_CHANGED: track power on.
        z21.send_to(&[0x08, 0x00, 0x40, 0x00, 0x62, 0x22, 0x00, 0x40], client)
            .unwrap();
    });
    let mut station = Z21Station::connect("127.0.0.1", port).unwrap();
    answer.join().unwrap();
    assert_eq!(station.events(), [StationEvent::Power(true)]);
    station.set_power(false).unwrap();
    let deadline = Instant::now() + TIMEOUT;
    while !station.events().contains(&StationEvent::Disconnected) {
        assert!(Instant::now() < deadline, "ERROR no Disconnected event");
        std::thread::sleep(Duration::from_millis(20));
    }
}
