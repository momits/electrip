//! `electrip-sim-z21 [address]`: runs the Z21 simulator on a UDP address,
//! by default `127.0.0.1:21105`.

use std::net::UdpSocket;
use std::process::ExitCode;

fn main() -> ExitCode {
    let addr = std::env::args()
        .nth(1)
        .unwrap_or_else(|| format!("127.0.0.1:{}", electrip_sim_z21::PORT));
    let result = UdpSocket::bind(&addr).and_then(|socket| {
        println!("Z21 simulator on {}", socket.local_addr()?);
        electrip_sim_z21::serve(socket)
    });
    if let Err(e) = result {
        eprintln!("ERROR {addr}: {e}");
    }
    ExitCode::FAILURE
}
