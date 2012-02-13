#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository import Gtk

class DateiLadenDialog(Gtk.FileChooserDialog):
	def __init__(self, parent_window):
		super(DateiLadenDialog, self).__init__("Datei laden ...", parent_window, Gtk.FileChooserAction.OPEN, (Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN,Gtk.ResponseType.OK))
		self.set_default_response(Gtk.ResponseType.OK)
		self.add_filter(ElectripFileFilter())
		self.add_filter(AllFileFilter())

class BildLadenDialog(Gtk.FileChooserDialog):
	def __init__(self, parent_window):
		super(BildLadenDialog, self).__init__("Bild auswählen ...", parent_window, Gtk.FileChooserAction.OPEN, (Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN,Gtk.ResponseType.OK))
		self.set_default_response(Gtk.ResponseType.OK)
		self.add_filter(BildFileFilter())
		self.add_filter(AllFileFilter())

class DateiSpeichernDialog(Gtk.FileChooserDialog):
	def __init__(self, parent_window):
		super(DateiSpeichernDialog, self).__init__("Datei speichern ...", parent_window, Gtk.FileChooserAction.SAVE, (Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_SAVE,Gtk.ResponseType.OK))
		self.set_default_response(Gtk.ResponseType.OK)
		self.set_do_overwrite_confirmation(True)
		self.add_filter(ElectripFileFilter())
		self.add_filter(AllFileFilter())
		
class ElectripFileFilter(Gtk.FileFilter):
	def __init__(self):
		super(ElectripFileFilter, self).__init__()
		self.set_name("ELECTRIP-Dateien")
		self.add_pattern("*.elc")

class BildFileFilter(Gtk.FileFilter):
	def __init__(self):
		super(BildFileFilter, self).__init__()
		self.set_name("Bilder")
		self.add_pattern("*.png")
		self.add_pattern("*.jpg")
		self.add_pattern("*.bmp")
		self.add_pattern("*.gif")

class AllFileFilter(Gtk.FileFilter):
	def __init__(self):
		super(AllFileFilter, self).__init__()
		self.set_name("Alle Dateien")
		self.add_pattern("*")
