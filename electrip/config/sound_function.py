#!/usr/bin/env python
# -*- coding: UTF 8 -*-


class SoundFunction:
    """
    A Function consisting of :class:`SoundSegment`-
    objects, used to determine the sound to be played at
    a certain speed.
    """
    def __init__(self, segments):
        self.segments = segments
        
    def get_sound(self, x, sound_type):
        """
        Returns the sound of type *sound_type*
        from the segment at position *x*.
        Example::
        
            func = SoundFunction(various_diesel_sound_segments)
            sound = func.get_sound(67.0, "load_sound")
            
            # 'sound' now stores the filepath to
            # the "load_sound" of the segment at 67.0 km/h
        """
        nr = self.get_segment_nr_from_x(x)
        if nr is not None:
            return getattr(self.segments[nr], sound_type)
        
    def get_segment_nr_from_x(self, x):
        """
        Returns the number of the :class:`SoundSegment`
        belonging to the x-coordinate *x*.
        """
        if x == 0:
            return -1
        else:
            for nr, segment in enumerate(self.segments):
                if segment.start < x <= segment.end:
                    return nr
                    break