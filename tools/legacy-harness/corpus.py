"""Writes complete Electrip 1 configurations for the corpus (B-21), made by
the unmodified code in legacy/ from the loco packages (B-20).

Usage: python3 corpus.py <packages dir> <output dir>

See README.md for the written files.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import harness  # also keeps legacy/ free of bytecode

# Stands in for the temporary home, so the files do not depend on the run.
HOME = "/home/electrip"


def load_packages(model, packages_dir, names):
    """Loads packages like the import button of Electrip 1, which unpacks
    each one next to its zip file below ~/Lokomotiven."""
    locos_dir = Path(os.environ["HOME"]) / "Lokomotiven"
    locos_dir.mkdir(exist_ok=True)
    for name in names:
        zip_path = locos_dir / f"{name}.zip"
        shutil.copy(packages_dir / f"{name}.zip", zip_path)
        model.locos.append(model.load_loco(str(zip_path)))


def save(model, path):
    model.save(str(path))
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(os.environ["HOME"], HOME), encoding="utf-8")


def empty(config):
    """A new configuration as Electrip 1 saves it before any change."""
    return config.JsonModel()


def packages(config, packages_dir):
    """All loco packages plus a loco added with default values."""
    model = config.JsonModel()
    names = sorted(p.stem for p in packages_dir.glob("*.zip"))
    load_packages(model, packages_dir, names)
    model.locos.append(config.Loco(model.unsaved_changes))
    return model


def settings(config, packages_dir):
    """Two packages with changed settings and fields the packages leave at
    their defaults."""
    model = config.JsonModel()
    load_packages(model, packages_dir, ["BR 216", "V 60"])
    server = model.server
    server.host, server.port, server.bus, server.power = "192.168.0.111", 4304, 2, False
    joystick = model.joystick
    joystick.emergency_button, joystick.reverse_button = 9, 8
    joystick.accel_axis, joystick.axis_threshold = 1, 0.1
    joystick.focus_button, joystick.sound_button = 5, 6
    joystick.use_auto_focus, joystick.show_function_nr = False, True
    model.sound.sampling_rate, model.sound.show_level_bar = 22050, False

    loco = model.locos[1]
    loco.speed_to_step_func.load([(0.0, 0.0), (10.0, 20.0), (60.0, 128.0)])
    loco.protocol, loco.speed_steps, loco.address = "M 2", 28, 78
    loco.functions.append(
        config.DecoderFunction(model.unsaved_changes, "Kupplung", 2, False, 3, config.ToggleMode.PUSH)
    )
    loco.event_sounds.append(
        config.EventSound(
            model.unsaved_changes, "Anfahren", True, 4, loco.function_sounds[0].file_path,
            False, 0.0, 5.0, 0.5, None, 500, 1000, True,
        )
    )
    return model


def main():
    packages_dir = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    # Electrip 1 translates default names at import time.
    os.environ["LANGUAGE"] = "de"
    with tempfile.TemporaryDirectory() as tmp:
        harness.setup(tmp)
        from electrip import config

        save(empty(config), out / "empty.json")
        save(packages(config, packages_dir), out / "packages.json")
        save(settings(config, packages_dir), out / "settings.json")


if __name__ == "__main__":
    main()
