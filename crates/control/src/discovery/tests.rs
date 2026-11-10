// Test code: unwrap is allowed (AGENTS.md).
#![allow(clippy::unwrap_used)]

use super::*;

const STATION: &str = "192.168.1.5:4303:1";

fn seen(instance: u64, station: &str, status: Status) -> Announcement {
    Announcement {
        instance,
        station: station.into(),
        status,
        address: SocketAddr::from(([192, 168, 1, instance as u8], 4711)),
    }
}

#[test]
fn alone_the_instance_becomes_host() {
    assert_eq!(elect(5, STATION, &[]), Election::Host);
}

#[test]
fn the_instance_connects_to_the_host_of_its_station() {
    let others = [
        seen(9, "192.168.1.6:4303:1", Status::Host),
        seen(7, STATION, Status::Host),
    ];
    assert_eq!(
        elect(5, STATION, &others),
        Election::Connect(others[1].address)
    );
}

#[test]
fn of_two_hosts_the_one_with_the_smaller_id_stays_host() {
    let others = [
        seen(8, STATION, Status::Host),
        seen(7, STATION, Status::Host),
    ];
    assert_eq!(
        elect(5, STATION, &others),
        Election::Connect(others[1].address)
    );
}

#[test]
fn of_instances_starting_together_the_smallest_id_becomes_host() {
    let starting = [
        seen(5, STATION, Status::Searching),
        seen(9, STATION, Status::Searching),
    ];
    assert_eq!(elect(5, STATION, &starting), Election::Host);
    assert_eq!(elect(9, STATION, &starting), Election::Wait);
    assert_eq!(elect(9, STATION, &starting[1..]), Election::Host);
}

#[test]
fn clients_and_other_stations_do_not_count() {
    let others = [
        seen(1, STATION, Status::Client),
        seen(2, "192.168.1.6:4303:1", Status::Searching),
    ];
    assert_eq!(elect(5, STATION, &others), Election::Host);
}

#[test]
fn a_host_yields_only_to_a_host_with_a_smaller_id() {
    let others = [
        seen(3, STATION, Status::Host),
        seen(4, STATION, Status::Host),
        seen(1, STATION, Status::Client),
        seen(2, "192.168.1.6:4303:1", Status::Host),
    ];
    assert_eq!(yields_to(5, STATION, &others), Some(others[0].address));
    assert_eq!(yields_to(3, STATION, &others), None);
}

fn resolved(version: &str) -> ResolvedService {
    let properties = [
        ("id", "00000000000000ff"),
        ("version", version),
        ("station", STATION),
        ("status", "host"),
    ];
    let info = ServiceInfo::new(
        SERVICE,
        "x",
        "x.local.",
        "192.168.1.7",
        4711,
        &properties[..],
    );
    info.unwrap().as_resolved_service()
}

#[test]
fn an_announcement_is_read_from_the_service() {
    let expected = Announcement {
        instance: 255,
        station: STATION.into(),
        status: Status::Host,
        address: "192.168.1.7:4711".parse().unwrap(),
    };
    assert_eq!(
        announcement(&resolved(&VERSION.to_string())),
        Some(expected)
    );
    assert_eq!(announcement(&resolved("0")), None);
}

#[test]
fn the_station_id_has_the_lan_address_instead_of_localhost() {
    let station = Station::default();
    let id = station_id(&station);
    assert!(id.ends_with(":4303:1"), "{id}");
    assert!(!id.starts_with("127."), "{id}");
    let remote = Station {
        host: "192.168.1.5".into(),
        ..Station::default()
    };
    assert_eq!(station_id(&remote), STATION);
}
