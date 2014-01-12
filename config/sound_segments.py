#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler
from sound_engines import EngineType

"""
Different types of sound
"""

class SegmentPosition:
    MIDDLE = 1
    UPPER = 2

def create_sound_segment(engine_type, *args):
    """
    Returns a newly created 'SoundSegment'
    according to 'engine_type'.
    """
    if engine_type == EngineType.STEAM:
        return SteamSoundSegment(*args)
    elif engine_type == EngineType.DIESEL:
        return DieselSoundSegment(*args)

class SoundSegment(UnsavedChangesHandler):
    """
    Segment reaching from 'start' to 'end' where
    (start, end] represents the speed-range this
    segment covers.
    """
    position = SegmentPosition.MIDDLE
    def __init__(self, save_status_method, start, end):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.start = start
        self.end = end
    
class DieselSoundSegment(SoundSegment):
    """
    A segment for Diesel-sound, specifying the sound to
    be played for different conditions.
    Case 1: engine is running at constant speed
        a) engine is under load -> 'load_sound'
        b) else -> 'idle_sound'
    Case 2: engine is accelerating -> 'accel_sound'
    Case 3: engine is decelerating -> 'decel_sound'
    """
    type = "diesel"
    attributes = {SegmentPosition.UPPER: ["start",
                                          "end",
                                          "load_sound",
                                          "accel_sound",
                                          "decel_sound"],
                  SegmentPosition.MIDDLE: ["start",
                                           "end",
                                           "load_sound",
                                           "idle_sound",
                                           "accel_sound",
                                           "decel_sound"]}
    position = SegmentPosition.MIDDLE
    
    def __init__(self,
                 save_status_method,
                 start,
                 end,
                 load_sound=None,
                 idle_sound=None,
                 accel_sound=None,
                 decel_sound=None):
        SoundSegment.__init__(self, save_status_method, start, end)
        self.load_sound = load_sound
        self.idle_sound = idle_sound
        self.accel_sound = accel_sound
        self.decel_sound = decel_sound
                
    def set_position(self, position):
        """
        Creates the 'idle_sound'-attribute if position
        is 'SegmentPosition.MIDDLE', erases it if position
        is 'SegmentPosition.UPPER' (upper DieselSegments
        can't have an 'idle_sound').
        """
        if position != self.position:
            if position == SegmentPosition.MIDDLE:
                self.idle_sound = None
                self.position = SegmentPosition.MIDDLE
            elif position == SegmentPosition.UPPER:
                del self.idle_sound
                self.position = SegmentPosition.UPPER

class SteamSoundSegment(SoundSegment):
    """
    A segment for Steam-sound, specifying the sound
    of the cylinder-strokes of the steam loco during
    the speed-range (start, end}.
    """
    type = "steam"
    def __init__(self,
                 save_status_method,
                 start,
                 end,
                 stroke_sounds=None):
        SoundSegment.__init__(self, save_status_method, start, end)
        self.stroke_sounds = stroke_sounds
        
    def set_position(self, position):
        """
        Does nothing at all, position doesn't matter for
        'SteamSoundSegment's.
        """
