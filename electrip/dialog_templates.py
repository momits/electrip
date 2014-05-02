#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository import Gtk

"""
This module contains specialized Gtk.Dialogs used to
retrieve certain input from the user.
"""

class WarningDialog(Gtk.MessageDialog):
    def __init__(self, parent_window, warning_text, buttons):
        Gtk.MessageDialog.__init__(self,
                                   parent_window,
                                   0,
                                   Gtk.MessageType.WARNING,
                                   Gtk.ButtonsType.NONE,
                                   warning_text)
        self.add_buttons(*buttons)

class FileLoadDialog(Gtk.FileChooserDialog):
    def __init__(self, parent_window, filters=None):
        Gtk.FileChooserDialog.__init__(self,
                                       "Datei laden ...",
                                       parent_window,
                                       Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL,
                                        Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN,
                                        Gtk.ResponseType.OK))
        self.set_default_response(Gtk.ResponseType.OK)
        self.add_filter(ElectripFileFilter())
        self.add_filter(AllFileFilter())
        
class FileSetResetDialog(Gtk.FileChooserDialog):
    def __init__(self, filters=None):
        Gtk.FileChooserDialog.__init__(self,
                                       "Datei auswählen ...",
                                       None,
                                       Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL,
                                        Gtk.ResponseType.CANCEL,
                                        "Zurücksetzen",
                                        2,
                                        Gtk.STOCK_OPEN,
                                        Gtk.ResponseType.OK))
        self.set_default_response(Gtk.ResponseType.OK)
        

class SoundLoadDialog(Gtk.FileChooserDialog):
    def __init__(self, parent_window, filters=None):
        Gtk.FileChooserDialog.__init__(self,
                                       "Geräusch auswählen ...",
                                       parent_window,
                                       Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL,
                                        Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN,
                                        Gtk.ResponseType.OK))
        self.set_default_response(Gtk.ResponseType.OK)
        self.add_filter(SoundFileFilter())
        self.add_filter(AllFileFilter())
        
class LocoLoadDialog(Gtk.FileChooserDialog):
    def __init__(self, parent_window):
        Gtk.FileChooserDialog.__init__(self,
                                       "Lok auswählen ...",
                                       parent_window,
                                       Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL,
                                        Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN,
                                        Gtk.ResponseType.OK))
        self.set_default_response(Gtk.ResponseType.OK)
        self.add_filter(LocoFileFilter())
        self.add_filter(AllFileFilter())

class FileSaveDialog(Gtk.FileChooserDialog):
    def __init__(self, parent_window, filters=None):
        Gtk.FileChooserDialog.__init__(self,
                                       "Datei speichern ...",
                                       parent_window,
                                       Gtk.FileChooserAction.SAVE,
                                       (Gtk.STOCK_CANCEL,
                                        Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_SAVE,
                                        Gtk.ResponseType.OK))
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_do_overwrite_confirmation(True)
        self.add_filter(ElectripFileFilter())
        self.add_filter(AllFileFilter())
        
class LocoSaveDialog(Gtk.FileChooserDialog):
    def __init__(self, parent_window, filters=None):
        Gtk.FileChooserDialog.__init__(self,
                                       "Lok speichern ...",
                                       parent_window,
                                       Gtk.FileChooserAction.SELECT_FOLDER,
                                       (Gtk.STOCK_CANCEL,
                                        Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_SAVE,
                                        Gtk.ResponseType.OK))
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_do_overwrite_confirmation(True)
        
class ElectripFileFilter(Gtk.FileFilter):
    def __init__(self):
        Gtk.FileFilter.__init__(self)
        self.set_name("ELECTRIP-Dateien")
        self.add_pattern("*.json")

class ImageFileFilter(Gtk.FileFilter):
    def __init__(self):
        Gtk.FileFilter.__init__(self)
        self.set_name("Bilder")
        self.add_pattern("*.png")
        self.add_pattern("*.jpg")
        self.add_pattern("*.bmp")
        self.add_pattern("*.gif")
        
class LocoFileFilter(Gtk.FileFilter):
    def __init__(self):
        Gtk.FileFilter.__init__(self)
        self.set_name("Lokomotiv-Dateien")
        self.add_pattern("*.loco")
        self.add_pattern("*.zip")
        
class SoundFileFilter(Gtk.FileFilter):
    def __init__(self):
        Gtk.FileFilter.__init__(self)
        self.set_name("Sound-Dateien")
        self.add_pattern("*.ogg")
        self.add_pattern("*.wav")

class AllFileFilter(Gtk.FileFilter):
    def __init__(self):
        Gtk.FileFilter.__init__(self)
        self.set_name("Alle Dateien")
        self.add_pattern("*")
