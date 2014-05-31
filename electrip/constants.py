#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os.path import normpath as _

# ELECTRIP-Constants

# ----------- General -----------

ELECTRIP_VERSION = "5.0.8"

ICON_PATHS = (_("icons/logo_icon_128.png"),
              _("icons/logo_icon_64.png"),
              _("icons/logo_icon_48.png"),
              _("icons/logo_icon_32.png"))

CIRCLE_PATHS = {"loco_function": _("icons/loco_function_circle.png"),
                "function_sound": _("icons/function_sound_circle.png"),
                "event_sound": _("icons/event_sound_circle.png"),
                "speed_sound": _("icons/speed_sound_circle.png")}

RELOAD_GRAPH_IMAGE_PATH = _("icons/reload_graph.png")

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
    