#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os.path import normpath as _

# ELECTRIP-Constants

# ----------- General -----------

ELECTRIP_VERSION = "4.15.1"

ICON_PATHS = (_("Icons/logo_icon_128.png"),
              _("Icons/logo_icon_64.png"),
              _("Icons/logo_icon_48.png"),
              _("Icons/logo_icon_32.png"))

CIRCLE_PATHS = {"loco_function": _("Icons/loco_function_circle.png"),
                "function_sound": _("Icons/function_sound_circle.png"),
                "event_sound": _("Icons/event_sound_circle.png"),
                "speed_sound": _("Icons/speed_sound_circle.png")}

RELOAD_GRAPH_IMAGE_PATH = _("Icons/reload_graph.png")

# ----------- Configuration -----------

PROTOCOLS = {"M 1": (80, 1, (14,)),
             "M 2": (255, 5, (14, 28)),
             "N 1": (10239, 32, (14, 28, 128)),
             "N 2": (10239, 32, (14, 28, 128))}

class EntryType:
    STRING = 0 # Entry for text
    INT = 1 # Entry for Integer
    FLOAT = 2 # Entry for Float
    COMBO = 3 # ComboBox
    BOOL = 4 # CheckButton
    SOUND_FILE = 5 # Button that opens a file-selection-dialog for sounds
    IMAGE_FILE = 6 # Button that opens a file-selection-dialog for images
    VOLUME = 7 # Volume Slider
    BUTTON = 8 # Button which can be connected to a custom callback
    LABEL = 9 # Label
#    CUSTOM = 10 # custom widget
    
class CellType:
    TEXT = 0
    COMBO = 1
    TEXT_NOT_EDITABLE = 2
    
# ----------- Control -----------

class ToggleMode:
    SWITCH = 0 # first click = On, second click = Off
    PUSH = 1 # button-pressed = On, button-released = Off
    PUSH_LIMITED = 2 # button-pressed = On, button-released = Off, program may turn Off earlier
    TAP = 3 # first click = On, program decides when Off
    
SOUND_LEVEL_ANIM_RES = 500.0 # the number of steps the sound-level-animation performs when traversing the whole speed-scale

# ----------- Sound -----------

class EngineType:
    STEAM = "steam"
    DIESEL = "diesel"

class SoundType:
    LOAD = "load"
    IDLE = "idle"
    ACCEL = "accel"
    DECEL = "decel"
    
class SegmentPosition:
    MIDDLE = 1
    UPPER = 2
    
#class FunctionType:
#    MONOTONIC_INCREASE = 0
#    MONOTONIC_DECREASE = 1

END_EVENT_LOWER_BOUND = 35
STOP_EVENT = 25
    