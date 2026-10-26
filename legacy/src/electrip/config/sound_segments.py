#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from .unsaved_changes import UnsavedChangesHandler
from .sound_engines import EngineType

"""
Classes providing abstractions for different types of sounds.
"""

class SegmentPosition:
    """
    Defines two types of Segments: upper and middle
    ones. Used e.g. in :func:`SoundSegment.set_position`.
    """
    MIDDLE = 1
    UPPER = 2

def create_sound_segment(engine_type, *args):
    """
    Returns a newly created :class:`SoundSegment`
    according to *engine_type*.
    """
    if engine_type == EngineType.STEAM:
        return SteamSoundSegment(*args)
    elif engine_type == EngineType.DIESEL:
        return DieselSoundSegment(*args)

class SoundSegment(UnsavedChangesHandler):
    """
    Defines sounds for a certain speed-range
    reaching from speeds greater than *start* to
    speeds smaller or equal to *end*.
    """
    def __init__(self, save_status_method, start, end):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.start = start
        self.end = end
        self.position = SegmentPosition.MIDDLE
        
    def set_position(self):
        """
        Allows segment-implementations to react to
        position-changes. Should be called whenever the position
        of a segment changes.
        """
        raise RuntimeError("Method 'set_position' must be"
                           "implemented in a child class.")
    
class DieselSoundSegment(SoundSegment):
    """
    A segment for Diesel-sound.
    Provides different sounds for different conditions:
    
        * *load_sound*: engine is running under load at
          constant speed
        * *idle_sound*: engine is running idle at
          constant speed
        * *accel_sound*: engine is accelerating
        * *accel_sound*: engine is decelerating
    """
    
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
        
        self.type = "diesel"
        self.attributes = {SegmentPosition.UPPER: ["start",
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
                
    def set_position(self, position):
        """
        Creates the *idle_sound*-attribute if position
        is *SegmentPosition.MIDDLE*, erases it if position
        is *SegmentPosition.UPPER* (in the upper
        *DieselSoundSegment* the loco is always under load).
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
    A segment for steam-sound. Provides the attribute
    *stroke_sounds*, which is a list of strings specifying the
    sound-filepaths for the cylinder-strokes.
    E.g.::
    
        segment = SteamSoundSegment(some_method,
                                    12.0,
                                    31.2,
                                    ["/home/user/tchoo.wav",
                                     "/home/user/piff.wav",
                                     "/home/user/paff.wav"])
        # if active, tchoo-piff-paff-tchoo-piff-paff-tchoo...
        # should be played
    
    will create a new :class:`SteamSoundSegment` reaching from
    any speed greater than 12.0 km/h to 31.2 km/h. If active,
    :file:`tchoo.wav`, :file:`piff.wav` and :file:`paff.wav`.
    should be used as cylinder-stroke-sounds.
    """
    def __init__(self,
                 save_status_method,
                 start,
                 end,
                 stroke_sounds=None):
        SoundSegment.__init__(self, save_status_method, start, end)
        self.stroke_sounds = stroke_sounds
        
        self.type = "steam"
        
    def set_position(self, position):
        """
        Does nothing at all, position doesn't matter for
        :class:`SteamSoundSegment`.
        """
