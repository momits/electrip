#!/usr/bin/env python
# -*- coding: utf-8 -*-
import gettext

from electrip.constants import LOCALE_PATH, APP_ID
from electrip.utils import TwoWayDict
from electrip import config

_ = gettext.translation(APP_ID + "-configuration", localedir=LOCALE_PATH).gettext

on_off = TwoWayDict()
on_off[_("On")] = True
on_off[_("Off")] = False

yes_no = TwoWayDict()
yes_no[_("Yes")] = True
yes_no[_("No")] = False

toggle_mode = TwoWayDict()
toggle_mode[_("Switch")] = config.ToggleMode.SWITCH
toggle_mode[_("Push-button")] = config.ToggleMode.PUSH

sound_toggle_mode = TwoWayDict()
sound_toggle_mode[_("Switch")] = config.ToggleMode.SWITCH
sound_toggle_mode[_("Push-button (play repeatedly)")] = config.ToggleMode.PUSH
sound_toggle_mode[_("Push-button (play once)")] = config.ToggleMode.PUSH_LIMITED
sound_toggle_mode[_("Tap (play until end)")] = config.ToggleMode.TAP

direction = TwoWayDict()
direction[_("Forward")] = True
direction[_("Backward")] = False

protocols = TwoWayDict()
protocols["M 1"] = _("Märklin Motorola Version 1")
protocols["M 2"] = _("Märklin Motorola Version 2")
protocols["N 1"] = _("DCC with short adresses")
protocols["N 2"] = _("DCC with long adresses")

doesnt_matter = _("Any")


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
