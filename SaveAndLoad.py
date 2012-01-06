#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk

class DateiLadenDialog(gtk.FileChooserDialog):
	def __init__(self, parent_window):
		gtk.FileChooserDialog.__init__(self, "Datei laden ...", parent_window, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN,gtk.RESPONSE_OK))
		self.set_default_response(gtk.RESPONSE_OK)
		self.add_filter(ElectripFileFilter())
		self.add_filter(AllFileFilter())

class DateiSpeichernDialog(gtk.FileChooserDialog):
	def __init__(self, parent_window):
		gtk.FileChooserDialog.__init__(self, "Datei speichern ...", parent_window, gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
		self.set_default_response(gtk.RESPONSE_OK)
		self.set_do_overwrite_confirmation(True)
		self.add_filter(ElectripFileFilter())
		self.add_filter(AllFileFilter())
		
class ElectripFileFilter(gtk.FileFilter):
	def __init__(self):
		gtk.FileFilter.__init__(self)
		self.set_name("ELECTRIP-Dateien")
		self.add_pattern("*.elc")

class AllFileFilter(gtk.FileFilter):
	def __init__(self):
		gtk.FileFilter.__init__(self)
		self.set_name("Alle Dateien")
		self.add_pattern("*")
