#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler
from linear_segment_function import LinearSegmentFunction

class Loco(UnsavedChangesHandler):
    """
    A model-train loco.
    """
    def __init__(self,
                 save_status_method,
                 functions=None,
                 speed_to_step_func=None,
                 function_sounds=None,
                 engine=None,
                 name="Unbenannte Lok",
                 speed_steps=128,
                 max_speed=100.0,
                 address=1,
                 protocol="N 1",
                 accel_duration=11.5,
                 decel_duration=8.5,
                 direction=True,
                 img_path=None,
                 sound_volume=0.8,):
        UnsavedChangesHandler.__init__(self, save_status_method)
        # it is not possible to set the default value for
        # the "functions"-parameter above, because it is
        # a list and will therefore contain pointers to the same objects
        # for all locos, resulting in the same functions for all locos
        if functions == None:
            self.functions = []
        else:
            self.functions = functions
        self.speed_steps = speed_steps
        if speed_to_step_func == None:
            self.speed_to_step_func = LinearSegmentFunction()
            self.speed_to_step_func.load([(0.0, 0.0), (100.0, 128.0)])
        else:
            self.speed_to_step_func = speed_to_step_func
        if function_sounds == None:
            self.function_sounds = []
        else:
            self.function_sounds = function_sounds
        self.name = name
        self.address = address
        self.protocol = protocol

        self.accel_duration = accel_duration
        self.decel_duration = decel_duration
        self.direction = direction
        self.img_path = img_path
        self.max_speed = max_speed
        self.speed = 0.0
        self.speed_step = 0.0
        self.last_speed_step = 0
        
        self.sound_volume = sound_volume
        self.engine = engine

    def get_srcp_status(self, bus):
        """
        Returns a SRCP-command representing the current
        state of the loco.
        """
        self.last_speed_step = int(self.speed_step)
        if len(self.functions) > 0:
            toggled = [False for unused_i in range(max([function.nr + 1 for function in self.functions]))]
            for function in self.functions:
                if function.state:
                    toggled[function.nr] = True
            functions = " " + " ".join(str(int(val)) for val in toggled)
        else:
            functions = ""
        return "SET " + str(bus) + " GL " + str(self.address) + " " \
                + str(int(self.direction)) + " " + str(int(self.speed_step)) \
                + " " + str(self.speed_steps) + functions + "\n"
    
    def accelerate(self, value):
        """
        Accelerates the loco by *value*. *value* must be a float
        between -1 and 1 representing the acceleration rate.
        If *value* is positive, the loco is accelerated
        with respect to ``loco.accel_duration``, if negative
        ``loco.decel_duration``.
        Returns the new speed of the loco.
        """
        if value >= 0:
            self.speed = min(self.max_speed,
                             max(0,
                                 self.speed + value *
                                 (0.05 / self.accel_duration * self.max_speed)))
        else:
            self.speed = min(self.max_speed,
                             max(0, self.speed + value *
                                 (0.05 / self.decel_duration * self.max_speed)))
        return self.speed
        
    def toggle_direction(self):
        self.direction = not self.direction
