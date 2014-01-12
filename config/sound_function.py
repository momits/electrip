#!/usr/bin/env python
# -*- coding: UTF 8 -*-

class SoundFunction:
    """
    A Function consisting of 'SoundSegments',
    used to determine the sound to be played at
    a certain speed.
    """
    def __init__(self, segments):
        self.segments = segments
        
    def get_sound(self, x, sound_type):
        """
        Returns the sound of type 'sound_type'
        from the segment at position 'x'.
        """
        nr = self.get_segment_nr_from_x(x)
        if nr != None:
            return getattr(self.segments[nr], sound_type)
        
    def get_segment_nr_from_x(self, x):
        """
        Returns the number of the SoundSegment
        belonging to the x-coordinate 'x'.
        """
        if x == 0:
            return -1
        else:
            for nr, segment in enumerate(self.segments):
                if segment.start < x <= segment.end:
                    return nr
                    break