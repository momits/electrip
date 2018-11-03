#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from sys import platform

# ELECTRIP-Constants


# ----------- General -----------

ELECTRIP_VERSION = "5.5.4"

PATH = os.path.dirname(os.path.realpath(__file__))

LOCALE_PATH = os.path.join(PATH, "locale")

ICON_PATHS = (os.path.join(PATH, "icons", "logo_icon_128.png"),
              os.path.join(PATH, "icons", "logo_icon_64.png"))

RELOAD_GRAPH_IMAGE_PATH = os.path.join(PATH, "icons", "reload_graph.png")

# path for settings
CONFIG_DIR = os.path.expanduser("~/.config/electrip")
if not os.path.exists(CONFIG_DIR):
    if platform.startswith("linux"):
        # create the directory
        os.makedirs(CONFIG_DIR, 0o700)
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