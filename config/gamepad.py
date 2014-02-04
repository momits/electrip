#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler

class Joystick(UnsavedChangesHandler):
    """
    Input device with knobs and axes, used to
    control the model railway.
    Used for general Gamepad-settings.
    """
    def __init__(self,
                 save_status_method,
                 emergency_button=0,
                 reverse_button=1,
                 accel_axis=2,
                 axis_threshold=0.06,
                 focus_button=3,
                 sound_button=4,
                 use_auto_focus=True,
                 show_function_nr=False):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.emergency_button = emergency_button
        self.reverse_button = reverse_button
        self.accel_axis = accel_axis
        self.axis_threshold = axis_threshold
        self.focus_button = focus_button
        self.sound_button = sound_button
        self.use_auto_focus = use_auto_focus
        self.show_function_nr = show_function_nr