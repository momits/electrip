#!/usr/bin/env python2.7
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler
from linear_segment_function import LinearSegmentFunction
import time


class Loco(UnsavedChangesHandler):
    """
    A model-train loco.
    """
    def __init__(self,
                 save_status_method,
                 functions=None,
                 speed_to_step_func=None,
                 function_sounds=None,
                 event_sounds=None,
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
        
        if speed_to_step_func == None:
            self.speed_to_step_func = LinearSegmentFunction()
            self.speed_to_step_func.load([(0.0, 0.0), (100.0, 128.0)])
        else:
            self.speed_to_step_func = speed_to_step_func
        
        if function_sounds == None:
            self.function_sounds = []
        else:
            self.function_sounds = function_sounds
        
        if event_sounds == None:
            self.event_sounds = []
        else:
            self.event_sounds = event_sounds
            
        self.engine = engine
        
        self.name = name
        self.speed_steps = speed_steps
        self.max_speed = max_speed
        self.address = address
        self.protocol = protocol

        self.accel_duration = accel_duration
        self.decel_duration = decel_duration
        self.direction = direction
        self.img_path = img_path
        
        # property 'speed' with getters and setters is used
        # to automatically update 'acceleration'
        self._speed = 0.0
        self._last_speed = 0.0
        self.acceleration = 0.0
        self._last_time = 0
        
        self.speed_step = 0.0
        self.last_speed_step = 0
        
        self.sound_volume = sound_volume
    
    @property
    def speed(self):
        return self._speed
    
    @speed.setter
    def speed(self, value):
        if value != self._speed:
            self._speed = value
            current_time = time.time()
            self.acceleration = (self._speed - self._last_speed) / \
                (current_time - self._last_time)
            self._last_time = current_time
            self._last_speed = self._speed

    @speed.deleter
    def speed(self):
        del self._speed
    
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
    
    def toggle_direction(self):
        self.direction = not self.direction
