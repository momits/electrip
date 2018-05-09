#!/usr/bin/env python
# -*- coding: utf-8 -*-

from electrip.utils import TwoWayDict
from electrip import config

on_off = TwoWayDict()
on_off["An"] = True
on_off["Aus"] = False

yes_no = TwoWayDict()
yes_no["Ja"] = True
yes_no["Nein"] = False

toggle_mode = TwoWayDict()
toggle_mode["Umschalter"] = config.ToggleMode.SWITCH
toggle_mode["Taster"] = config.ToggleMode.PUSH

sound_toggle_mode = TwoWayDict()
sound_toggle_mode["Umschalter"] = config.ToggleMode.SWITCH
sound_toggle_mode["Taster (mehrmals abspielen)"] = config.ToggleMode.PUSH
sound_toggle_mode["Taster (einmal abspielen)"] = config.ToggleMode.PUSH_LIMITED
sound_toggle_mode["Anschalter (bis Geräuschende)"] = config.ToggleMode.TAP

direction = TwoWayDict()
direction["Vorwärts"] = True
direction["Rückwärts"] = False

protocols = TwoWayDict()
protocols["M 1"] = "Märklin Motorola Version 1"
protocols["M 2"] = "Märklin Motorola Version 2"
protocols["N 1"] = "DCC kurzes Adressformat"
protocols["N 2"] = "DCC langes Adressformat"

doesnt_matter = "Egal"

def maybe_direction_to_str(maybe_direction):
    try:
        return direction[maybe_direction]
    except KeyError:
        return doesnt_matter
    
def str_to_maybe_direction(string):
    try:
        return direction[string]
    except KeyError:
        return None

def maybe_float_to_str(maybe_float):
    """
    Returns ``str(maybe_float)`` if ``maybe_float != None``,
    otherwise returns a string translatable to
    'doesn\'t' matter'.
    """
    return str(maybe_float).replace(".", ",") if maybe_float else doesnt_matter

def str_to_maybe_float(string):
    """
    Returns ``float(string)`` if  *string*
    can be converted to a float.
    Otherwise returns ``None``.
    """
    try:
        return float(string.replace(",", "."))
    except ValueError:
        return None
