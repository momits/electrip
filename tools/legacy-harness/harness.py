"""Runs a golden scenario against the unmodified Electrip 1 code in legacy/
and prints the recorded events as JSON Lines.

Usage: python3 harness.py <scenario.json>

See README.md for the scenario format and the recorded events.
"""

import json
import os
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True  # keep legacy/ untouched

import fakes  # noqa: E402

LEGACY = Path(__file__).resolve().parents[2] / "legacy" / "src"


def emit(entry):
    print(json.dumps(entry, ensure_ascii=False))


def record(entry):
    emit({"t": fakes.LOOP.now / 1_000_000, **entry})


def run_curves(curves):
    """B-08: speed steps of LinearSegmentFunction for given control points."""
    from electrip.config.linear_segment_function import LinearSegmentFunction

    for nr, curve in enumerate(curves):
        func = LinearSegmentFunction()
        func.load([tuple(p) for p in curve["points"]])
        emit({"curve": nr, "points": func.control_points})
        for x in curve["x"]:
            emit({"curve": nr, "x": x, "step": func.get_y(x)})


class SocketThread:
    """Stands in for concurrent.SRCPSocketThread and records the commands."""

    def __init__(self, unused_socket):
        pass

    def start(self):
        pass

    def wait_for_answer(self):
        return ""

    def send_and_wait_for_answer(self, cmd):
        record({"srcp": cmd.strip()})

    send_and_block_for_answer = send_and_wait_for_answer


def run_session(scenario, workdir):
    """Starts the control UI of Electrip 1 and replays the gamepad input."""
    from electrip import config, control_ui, pygame_io
    import electrip.config.loco as loco_module

    for module in (loco_module, pygame_io):
        module.time = fakes.time_module
    pygame_io.threading = fakes.threading_module
    pygame_io.isfile = lambda path: path in fakes.Mixer.lengths
    pygame_io.EventHandlerThread.start = lambda self: None
    control_ui.SRCPSocketThread = SocketThread
    control_ui.socket.create_connection = lambda address: None
    fakes.Mixer.lengths = scenario["sound_lengths"]
    fakes.Mixer.record = record

    path = workdir / "config.json"
    path.write_text(json.dumps(scenario["config"]))
    model = config.JsonModel()
    model.load(str(path))
    # The level bar is display only; without it no animation threads run.
    model.sound.show_level_bar = False
    main = control_ui.MainBox(model, None)

    hub = main.scrolled_window.controller_hub
    fakes.LOOP.pump = hub.event_thread.run
    accel_axis = control_ui.Config.joystick.accel_axis
    for step in scenario["input"]:
        fakes.LOOP.at(fakes.to_us(step["t"]), lambda s=step: apply_input(s, accel_axis))
    fakes.LOOP.run_until(fakes.to_us(scenario["until"]))
    if fakes.LOOP.errors:
        raise RuntimeError("errors in threads: " + "; ".join(fakes.LOOP.errors))


def apply_input(step, accel_axis):
    record({"input": {k: v for k, v in step.items() if k != "t"}})
    if "axis" in step:
        fakes.Joystick.axes[accel_axis] = step["axis"]
        if step["axis"] == 0:
            post(fakes.JOYAXISMOTION, axis=accel_axis, value=0)
    elif "press" in step:
        post(fakes.JOYBUTTONDOWN, button=step["press"])
    elif "release" in step:
        post(fakes.JOYBUTTONUP, button=step["release"])


def post(event_type, **fields):
    fakes.Pygame.post(types.SimpleNamespace(type=event_type, joy=0, **fields))


def setup(tmp):
    """Makes legacy/ importable with fakes and an empty home in *tmp*."""
    # Electrip 1 writes last_file.json below $HOME or into the cwd.
    workdir = Path(tmp)
    (workdir / ".config" / "electrip").mkdir(parents=True)
    os.environ["HOME"] = tmp
    os.chdir(tmp)
    sys.path.insert(0, str(LEGACY))
    fakes.install_gi()
    fakes.install_pygame()
    return workdir


def main():
    scenario = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        workdir = setup(tmp)
        if "curves" in scenario:
            run_curves(scenario["curves"])
        else:
            run_session(scenario, workdir)


if __name__ == "__main__":
    main()
