#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os.path import expanduser, exists, normpath as _
from os import makedirs
from sys import platform

# ELECTRIP-Constants


# ----------- General -----------

ELECTRIP_VERSION = "5.4.0"

ICON_PATHS = (_("icons/logo_icon_128.png"),
              _("icons/logo_icon_64.png"))

RELOAD_GRAPH_IMAGE_PATH = _("icons/reload_graph.png")

# path for settings
CONFIG_DIR = expanduser("~/.config/electrip")
if not exists(CONFIG_DIR):
    if platform.startswith("linux"):
        # create the directory
        makedirs(CONFIG_DIR, 0o700)
    else:
        # allow bundles on other OS to save settings locally
        CONFIG_DIR = ""


# ----------- Configuration -----------

PROTOCOLS = {"M 1": (80, 1, (14,)),
             "M 2": (255, 5, (14, 28)),
             "N 1": (10239, 32, (14, 28, 128)),
             "N 2": (10239, 32, (14, 28, 128))}


# ----------- Control -----------

# the number of steps the sound-level-animation performs when
# traversing the whole speed-scale
SOUND_LEVEL_ANIM_RES = 500.0


# ----------- Sound -----------


class SoundType:
    LOAD = "load"
    IDLE = "idle"
    ACCEL = "accel"
    DECEL = "decel"


END_EVENT_LOWER_BOUND = 35
STOP_EVENT = 25