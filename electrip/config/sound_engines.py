#!/usr/bin/env python
# -*- coding: UTF 8 -*-

"""
Contains the different sound implementations.
"""

from unsaved_changes import UnsavedChangesHandler
from sound_function import SoundFunction


class EngineType:
    """
    Defines all possible engine types
    for sound generation.
    
        * *STEAM*: A steam engine
        * *DIESEL*: A diesel engine
    """
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
    Abstract representation of an engine which
    has some kind of sound.
    *sound_segments* is a list of :class:`SoundSegment`-
    objects defining the sound of the engine at
    different speed-ranges.
    *event_sounds* is a list of :class:`EventSound`-
    objects defining sounds which should be played under
    certain conditions.
    """
    def __init__(self,
                 save_status_method,
                 sound_segments):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.sound_segments = sound_segments
        if self.sound_segments:
            self.sound_function = SoundFunction(self.sound_segments)
        else:
            self.sound_function = None


class DieselEngine(Engine):
    """
    A Diesel-powered engine. It has *start_sound*,
    *idle_sound* and *quit_sound* attributes,
    which are strings containing the path
    to the sound-files representing the off-on-transition,
    idle-state and on-off-transition of the engine.
    For *sound_segments* and *event_sounds* see
    :class:`Engine`.
    """
    def __init__(self,
                 save_status_method,
                 start_sound=None,
                 idle_sound=None,
                 quit_sound=None,
                 sound_segments=None):
        Engine.__init__(self,
                        save_status_method,
                        sound_segments)
        self.type = EngineType.DIESEL
        self.start_sound = start_sound
        self.idle_sound = idle_sound
        self.quit_sound = quit_sound


class SteamEngine(Engine):
    """
    | A steam-powered engine.
    
    Args:
        * *idle_sound*: sound which is played
          continuously, base noise of a steam-engine
        * *cylinder_steam_sound*: sound which is played
          when the engine starts to move, simulating
          steam coming out of the cylinder
        * *nr_strokes*: the number of cylinder strokes
          the engine performs (typically 4 on a 2 cylinder
          engine)
        * *stroke_start_delay*: the timespan the
          *cylinder_steam_sound* is played before the
          first stroke sound is played
        * *wheel_diameter*: diameter of the traction wheels
        * *min_freq*: minimal frequency of strokes / second,
          helps to avoid extremely long pauses between strokes
          at speeds near 0
        * *sound_segments*: see :class:`Engine`
        * *event_sounds*: see :class:`Engine`
    """
    def __init__(self,
                 save_status_method,
                 idle_sound=None,
                 cylinder_steam_sound=None,
                 nr_strokes=4,
                 stroke_start_delay=2.0,
                 wheel_diameter=1.2,
                 min_freq=0.2,
                 sound_segments=None):
        Engine.__init__(self,
                        save_status_method,
                        sound_segments)
        self.type = EngineType.STEAM
        self.idle_sound = idle_sound
        self.cylinder_steam_sound = cylinder_steam_sound
        self.nr_strokes = nr_strokes
        self.stroke_start_delay = stroke_start_delay
        self.wheel_diameter = wheel_diameter
        self.min_freq = min_freq
        self.sound_segments = sound_segments

