#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler

class ToggleMode:
    """
    Class used to specify different ways
    to toggle a button:
    
        * *SWITCH*: first click = on, second click = off
        * *PUSH*: button pressed = on, button released = off
        * *PUSH_LIMITED*: button pressed = on, button released = off,
          program may turn off earlier
        * *TAP*: first click = on, program decides when off
    """
    SWITCH = 0
    PUSH = 1
    PUSH_LIMITED = 2
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
        """
        Toggles the state of the funtion.
        """
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
    A :class:`LocoFunction` which defines conditions
    for the sound-file at *file_path* to be played.
    The sound should be played if
    
        * *min_speed* <= ``loco.speed`` <=  *max_speed*
        * *min_accel* <= ``derivation of loco.speed`` <=  *max_accel*
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
    A :class:`LocoFunction` which plays a sound-file
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
