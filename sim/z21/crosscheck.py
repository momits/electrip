"""Cross-check of the Z21 simulator with the independent client library z21aio.

Usage: python crosscheck.py [port]
Expects the simulator on 127.0.0.1 (default port 21105) and z21aio 1.0.7.
Two clients play the N-02 scenarios: one acts, the other must see the changes.
"""

import asyncio
import sys

from z21aio import Loco, Z21Station

HOST = "127.0.0.1"


async def next_item(queue: asyncio.Queue, what: str):
    try:
        return await asyncio.wait_for(queue.get(), timeout=2.0)
    except TimeoutError:
        raise SystemExit(f"ERROR no {what} within 2 s") from None


def check(condition: bool, what: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR {what}")
    print(f"ok    {what}")


async def main(port: int) -> None:
    watcher = await Z21Station.connect(HOST, port)
    driver = await Z21Station.connect(HOST, port)

    check(await driver.get_serial_number() > 0, "serial number")
    check(await driver.get_firmware_version() == (0x01, 0x43), "firmware version 1.43")
    check(await driver.get_version() == (0x30, 0x12), "X-Bus version and Z21 family")

    power = asyncio.Queue()
    watcher.subscribe_track_power(power.put_nowait)
    await driver.voltage_off()
    check(await next_item(power, "track power broadcast") is False, "watcher sees track power off")
    await driver.voltage_on()
    check(await next_item(power, "track power broadcast") is True, "watcher sees track power on")

    states = asyncio.Queue()
    watched = await Loco.control(watcher, address=3)
    watched.subscribe_state(states.put_nowait)
    loco = await Loco.control(driver, address=3)

    await loco.drive(50.0)
    state = await next_item(states, "loco info after drive")
    check(state.reverse is False and round(state.speed_percentage) == 50, "watcher sees speed 50 % forward")

    await loco.function_on(0)
    await next_item(states, "loco info after F0")
    await loco.function_on(28)
    state = await next_item(states, "loco info after F28")
    check(state.functions[0] and state.functions[28], "watcher sees F0 and F28 on")

    await loco.estop()
    state = await next_item(states, "loco info after emergency stop")
    check(state.is_estop, "watcher sees emergency stop of the loco")

    for station in (driver, watcher):
        await station.logout()
        await station.close()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 21105))
