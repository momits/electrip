#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler

class ToggleMode:
    # first click = On, second click = Off
    SWITCH = 0
    # button-pressed = On, button-released = Off
    PUSH = 1
    # button-pressed = On, button-released = Off, program may turn Off earlier
    PUSH_LIMITED = 2
    # first click = On, program decides when Off
    TAP = 3

class LocoFunction(UnsavedChangesHandler):
    """
    Function of a Loco with a name and a state triggered
    by a Gamepad-Button.
    """
    def __init__(self, save_status_method, name="", state=False, button=0):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.name = name
        self.state = state
        self.button = button
        
    def toggle(self):
        self.state = not self.state
        
class DecoderFunction(LocoFunction):
    """
    Function of the Decoder in a model-train loco.
    """
    def __init__(self,
                 save_status_method,
                 name="",
                 function=0,
                 state=False,
                 button=0,
                 toggle_mode=ToggleMode.SWITCH):
        LocoFunction.__init__(self,
                              save_status_method,
                              name,
                              state,
                              button)
        self.nr = function
        self.toggle_mode = toggle_mode
class EventSound(LocoFunction):
    """
    A 'LocoFunction' which plays a sound-file
    if certain conditions are met ('min_speed' ...)
    """
    def __init__(self,
                 save_status_method,
                 name="",
                 file_path=None,
                 state=True,
                 min_speed=None,
                 max_speed=None,
                 min_accel=None,
                 max_accel=None,
                 button=0):
        LocoFunction.__init__(self,
                              save_status_method,
                              name,
                              state,
                              button)
        self.file_path = file_path
        self.min_speed = min_speed
        self.max_speed = max_speed
        self.min_accel = min_accel
        self.max_accel = max_accel
        
class FunctionSound(LocoFunction):
    """
    A 'LocoFunction' which plays a sound-file
    if triggered via Gamepad.
    """
    def __init__(self,
                 save_status_method,
                 name="",
                 file_path=None,
                 state=False,
                 button=0,
                 toggle_mode=ToggleMode.TAP):
        LocoFunction.__init__(self,
                              save_status_method,
                              name,
                              state,
                              button)
        self.file_path = file_path
        self.toggle_mode = toggle_mode
