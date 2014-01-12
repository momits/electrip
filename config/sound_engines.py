#!/usr/bin/env python
# -*- coding: UTF 8 -*-

"""
Contains the different sound implementations.
"""

from unsaved_changes import UnsavedChangesHandler
from sound_function import SoundFunction

class EngineType:
    STEAM = "steam"
    DIESEL = "diesel"

def create_engine(engine_type, *args):
    """
    Returns a newly created 'Engine'
    according to 'engine_type'.
    """
    if engine_type == EngineType.DIESEL:
        return DieselEngine(*args)
    elif engine_type == EngineType.STEAM:
        return SteamEngine(*args)

class Engine(UnsavedChangesHandler):
    """
    
    """
    def __init__(self,
                 save_status_method,
                 sound_segments,
                 event_sounds):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.sound_segments = sound_segments
        if self.sound_segments != None:
            self.sound_function = SoundFunction(self.sound_segments)
        else:
            self.sound_function = None
        if event_sounds == None:
            self.event_sounds = []
        else:
            self.event_sounds = event_sounds

class DieselEngine(Engine):
    type = "diesel"
    def __init__(self,
                 save_status_method,
                 start_sound=None,
                 idle_sound=None,
                 quit_sound=None,
                 sound_segments=None,
                 event_sounds=None):
        Engine.__init__(self,
                        save_status_method,
                        sound_segments,
                        event_sounds)
        self.start_sound = start_sound
        self.idle_sound = idle_sound
        self.quit_sound = quit_sound
        
class SteamEngine(Engine):
    type = "steam"
    def __init__(self,
                 save_status_method,
                 idle_sound=None,
                 cylinder_steam_sound=None,
                 nr_strokes=4,
                 stroke_start_delay=2.0,
                 wheel_diameter=1.2,
                 min_freq=0.2,
                 sound_segments=None,
                 event_sounds=None):
        Engine.__init__(self,
                        save_status_method,
                        sound_segments,
                        event_sounds)
        self.idle_sound = idle_sound
        self.cylinder_steam_sound = cylinder_steam_sound
        self.nr_strokes = nr_strokes
        self.stroke_start_delay = stroke_start_delay
        self.wheel_diameter = wheel_diameter
        self.min_freq = min_freq
        self.sound_segments = sound_segments
        
