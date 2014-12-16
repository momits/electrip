#!/usr/bin/env python2.7
# -*- coding: UTF 8 -*-

class UnsavedChangesHandler(object):
    """
    An object which reports changes made to
    any of its attributes to a *save_status_method*
    (usually :func:`JsonModel.unsaved_changes`).
    """
    def __init__(self, save_status_method):
        # use object.__setattr__ to avoid calling our
        # own implementation already
        object.__setattr__(self, "callbacks", {})
        object.__setattr__(self, "attrib_name_to_watch_ids", {})
        if save_status_method:
            object.__setattr__(self, "save_status_method", save_status_method)
        object.__setattr__(self, "watch_count", 0)
    
    def __setattr__(self, name, value):
        try:
            for watch_id in self.attrib_name_to_watch_ids[name]:
                cb, args = self.callbacks[watch_id]
                cb(value, *args)
        except KeyError:
            pass
        object.__setattr__(self, name, value)
        if hasattr(self, "save_status_method"):
            self.save_status_method(self, name, value)
            
    def create_watch_id(self):
        self.watch_count += 1
        return self.watch_count
            
    def watch(self, attrib_name, cb, *args):
        """
        Allows you to track changes on
        *attrib_name* by providing a
        callback method *cb*.
        *cb* must be of the form::
        
        cb(new_value, arg1, arg2, ..., argn)
        
        where *arg1, ..., argn* are the elements
        stored in *args*.
        Returns a *watch_id* which can be used to
        remove the callback with :func:`stop_watching`.
        """
        watch_id = self.create_watch_id()
        self.callbacks[watch_id] = (cb, args)
        if self.attrib_name_to_watch_ids.has_key(attrib_name):
            self.attrib_name_to_watch_ids[attrib_name].append(watch_id)
        else:
            self.attrib_name_to_watch_ids[attrib_name] = [watch_id]
    
    def stop_watching(self, watch_id):
        """
        Removes the callback which was registered
        using :func:`watch` identified by *watch_id*.
        """
        del self.callbacks[watch_id]
        for attrib_name, watch_ids in self.attrib_name_to_watch_ids.items():
            if watch_id in watch_ids:
                watch_ids.remove(watch_id)
                # remove empty lists
                if not watch_ids:
                    del self.attrib_name_to_watch_ids[attrib_name]
                # every watch-id maps to exactly one attrib_name
                break
            
    def clean_up(self):
        """
        Removes all callbacks registered
        using :func:`watch`.
        The uniqueness of *watch_id*s is still guaranteed
        after calling this method.
        """
        self.callbacks = {}
        self.attrib_name_to_watch_ids = {}
