#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler

class Sound(UnsavedChangesHandler):
    """
    Used for basic settings concerning sound output.
    *sampling_rate* specifies the sampling rate Electrip
    should use for sound-playback.
    *show_level_bar* specifies whether an animated bar
    should be shown on the speed-scale to visualize
    sound-playback.
    """
    def __init__(self,
                 save_status_method,
                 sampling_rate=44100,
                 show_level_bar=True):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.sampling_rate = sampling_rate
        self.show_level_bar = show_level_bar
