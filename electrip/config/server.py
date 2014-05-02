#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from unsaved_changes import UnsavedChangesHandler

class Server(UnsavedChangesHandler):
    """
    SRCP-compatible Server.
    Used for all settings concerning
    TCP/IP connectivity.
    """
    def __init__(self,
                 save_status_method,
                 host="localhost",
                 port=4303,
                 bus=1,
                 power=True):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.host = host
        self.port = port
        self.bus = bus
        self.power = power
        
    def toggle_power(self):
        self.power = not self.power
        