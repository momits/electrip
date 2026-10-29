//! The simulator answers over a real UDP socket.

use std::net::UdpSocket;
use std::thread;
use std::time::Duration;

#[test]
fn serial_number_over_udp() -> std::io::Result<()> {
    let server = UdpSocket::bind("127.0.0.1:0")?;
    let server_addr = server.local_addr()?;
    thread::spawn(move || electrip_sim_z21::serve(server));

    let client = UdpSocket::bind("127.0.0.1:0")?;
    client.set_read_timeout(Some(Duration::from_secs(5)))?;
    client.send_to(&[0x04, 0x00, 0x10, 0x00], server_addr)?;
    let mut buf = [0u8; 64];
    let (len, from) = client.recv_from(&mut buf)?;
    assert_eq!(from, server_addr);
    assert_eq!(buf[..4], [0x08, 0x00, 0x10, 0x00]);
    assert_eq!(len, 8);
    Ok(())
}
