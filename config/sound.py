#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler

class Sound(UnsavedChangesHandler):
    """
    Representation for all settings concerning
    sound output.
    """
    def __init__(self,
                 save_status_method,
                 sampling_rate=44100,
                 show_level_bar=True):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.sampling_rate = sampling_rate
        self.show_level_bar = show_level_bar
