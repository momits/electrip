#!/usr/bin/env python
# -*- coding: UTF 8 -*-

class UnsavedChangesHandler(object):
    """
    An object which reports changes on any of its
    attributes to a 'save_status_method' (usually
    'Config.unsaved_changes').
    """
    def __init__(self, save_status_method):
        if save_status_method != None:
            self.save_status_method = save_status_method
    
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if hasattr(self, "save_status_method"):
            self.save_status_method(self, name, value)