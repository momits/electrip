#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from Constants import *
from gi.repository import GdkPixbuf, GLib
from LockedPrint import locked_print
try:
	import pygame
	from pygame.locals import * # Importiere Konstanten (JOYBUTTTONDOWN, ...) für kurze Namen
except ImportError:
	locked_print("PyGame ist nicht installiert, Joysticks können nicht verwendet werden.")
import threading

class JoystickKonsole():
	def __init__(self, loks, regler, nothaltbutton, joy_dict):
		global pygame
		pygame.init()
				
		self.AmLaufen = True # Status setzen
		pygame.joystick.init() # Joystick Modul initialisieren
		
		self.joysticks = []
		for id in range(pygame.joystick.get_count()):
			if not len(self.joysticks) == len(regler):
				self.joysticks.append([pygame.joystick.Joystick(id), id, 0]) # Liste mit Joystickobjekten erstellen Format: [joystick, zugehörige lok, start_scrolling (0 = Nein, 1 = Rechts, -1 = Links)] -> start_scrolling = True wenn joyhat 500 ms gedrückt wird
			else:
				locked_print("Joystick '" + pygame.joystick.Joystick(id).get_name() + "' wurde ignoriert, da ", pygame.joystick.get_count(), " Joysticks zuviel für ", len(regler), " Loks sind.")
		
		locked_print("Erkannte Joysticks:", len(self.joysticks))
		
		locked_print("\nJoystick - Initialisierung:")
		for joystick_lok in self.joysticks: # Daten der angeschlossenen Joysticks auslesen
			joystick = joystick_lok[0]
			locked_print("-------- " , joystick.get_id() , " --------")
			joystick.init() # Joystick initialisieren
			locked_print(joystick.get_name())
			locked_print("Anzahl Achsen:", joystick.get_numaxes())
			locked_print("Anzahl Knöpfe:", joystick.get_numbuttons(), "\n")
		
		self.joy_thread = JoystickThread(self.joysticks, loks, regler, nothaltbutton, joy_dict["Notstop"], joy_dict["Richtungswender"], joy_dict["Fokus"], joy_dict["AutoFokus"])
		self.joy_thread.start()
		self.geschw_thread = GeschwindigkeitsThread(self.joysticks, loks, regler, joy_dict["Achse"])
		self.geschw_thread_id = GObject.timeout_add(100, self.geschw_thread.go)
		
	
	def quit(self):
		locked_print("Stoppe Threads ...")
		self.joy_thread.quit()
		GObject.source_remove(self.geschw_thread_id)
		pygame.event.post(pygame.event.Event(MOUSEBUTTONDOWN, {"pos": 0, "button": 0})) # Event posten, um joystick_thread zu beenden

class JoystickThread(threading.Thread):
	def __init__(self, joystickliste, loks, regler, nothaltbutton, joy_button_notstop, joy_button_richtungswender, joy_button_set_focus, use_auto_focus):
		super(JoystickThread, self).__init__()
		self.bildliste = [GdkPixbuf.Pixbuf.new_from_file("Joystick/Pictures/" + str(bild_nr) + ".png") for bild_nr in range(1,13)]
			
		self.joysticks = joystickliste
		if len(self.joysticks) == 1 and use_auto_focus:
			self.auto_focus = True
		else:
			self.auto_focus = False
		locked_print("Auto-Fokus:", self.auto_focus)
		
		self.loks = loks
		self.regler = regler
		self.nothaltbutton = nothaltbutton
		
		self.joy_button_notstop = joy_button_notstop
		self.joy_button_richtungswender = joy_button_richtungswender
		self.joy_button_set_focus = joy_button_set_focus
		
		for joystick_lok in self.joysticks:
			self.regler[joystick_lok[1]].lokschild.set_bold(True)
			self.regler[joystick_lok[1]].gamepad_bild.set_from_pixbuf(self.bildliste[joystick_lok[1]])
			self.regler[joystick_lok[1]].joystick = joystick_lok[0]
		self.running = True
	
	def run(self):
		while self.running:
			event = pygame.event.wait()
			if event.type == JOYBUTTONDOWN:
				lokid = self.joysticks[event.joy][1]
				konfiguriert = False
				for funktion in self.loks[lokid].funktionen:
					if event.button == funktion["Button"]:
						GLib.idle_add(self.regler[lokid].hbox.buttons[funktion["Nr"]].clicked)
						konfiguriert = True
				if event.button == self.joy_button_richtungswender: # Gtk ist NICHT thread-safe, d.h. es können Probleme auftreten wenn von anderen threads Gtk-Objekte geändert werden
					GLib.idle_add(self.regler[lokid].richtungswender.clicked) # Deshalb: GLib.idle_add(Funktion, Parameter1, ...) -> Gtk-Hauptschleife führt Funktion mit Parametern aus, wenn sie Zeit hat
				elif event.button == self.joy_button_notstop:
					GLib.idle_add(self.nothaltbutton.clicked)
				elif event.button == self.joy_button_set_focus:
					GLib.idle_add(self.regler[lokid].set_focus) # Lässt die Gtk-Hauptschleife die Funktion Regler.set_focus aufrufen, verhindert raise-conditions die zum crash führen können
				elif not konfiguriert:  # Ist Button nicht in Lokfunktionen oder Spezialbuttons, ist er nicht konfiguriert
					locked_print("Nicht konfigurierter Button wurde gedrückt.")
					
			elif event.type == JOYBUTTONUP:
				lokid = self.joysticks[event.joy][1]
				for funktion in self.loks[lokid].funktionen:
					if event.button == funktion["Button"] and funktion["Taster"]:
						GLib.idle_add(self.regler[lokid].hbox.buttons[funktion["Nr"]].clicked)
						
			elif event.type == JOYHATMOTION:
				richtung = event.value[0]
				if richtung == 1 != self.joysticks[event.joy][2]:
					self.joysticks[event.joy][2] = 1 # Starte scroll-Prozess nach rechts wenn joyhat länger als 500 ms gedrückt wird
					self.scrollen(1, event.joy)
					GObject.timeout_add(JOYSTICK_SCROLL_ACTIVATE_TIME, self.set_auto_scroll, 1, event.joy)
				elif richtung == -1 != self.joysticks[event.joy][2]:
					self.joysticks[event.joy][2] = -1
					self.scrollen(-1, event.joy)
					GObject.timeout_add(JOYSTICK_SCROLL_ACTIVATE_TIME, self.set_auto_scroll, -1, event.joy)
				elif richtung == 0 != self.joysticks[event.joy][2]: # wenn joyhat losgelassen und noch gescrollt wird
					self.joysticks[event.joy][2] = 0 # richtung = 0 -> Scroll-Prozess wird gestoppt
				
		
	def lok_wechseln(self, lokid, neue_lokid, joystick):
		GLib.idle_add(self.regler[lokid].gamepad_bild.clear)
		GLib.idle_add(self.regler[lokid].lokschild.set_bold, False)
		self.regler[lokid].joystick = None
		GLib.idle_add(self.regler[neue_lokid].gamepad_bild.set_from_pixbuf, self.bildliste[joystick])
		GLib.idle_add(self.regler[neue_lokid].lokschild.set_bold, True)
		self.regler[neue_lokid].joystick = self.joysticks[joystick][0]
		if self.auto_focus: # Wenn nur ein Joystick, dann diesen fokussieren
			GLib.idle_add(self.regler[neue_lokid].set_focus) # Siehe oben
		lokid = neue_lokid
		self.joysticks[joystick][1] = lokid
		
	def scrollen(self, richtung, joystick):
		lokid = self.joysticks[joystick][1]
		if richtung == self.joysticks[joystick][2]:
			if richtung == 1 and lokid < len(self.regler)-1: # wenn lokid = länge von self.regler muss nicht gewechselt werden
				neue_lokid = lokid
				while neue_lokid < len(self.loks)-1 and self.regler[neue_lokid].joystick != None:
					neue_lokid += 1 # Findet nächste freie Lok-ID
				if self.regler[neue_lokid].joystick == None: # Prüfen, ob Lok frei ist (falls alle Loks mit Joysticks besetzt sind)
					self.lok_wechseln(lokid, neue_lokid, joystick)
				
			elif richtung == -1 and lokid > 0: # wenn lokid = 0 muss nicht gewechselt werden
				neue_lokid = lokid
				while neue_lokid > 0 and self.regler[neue_lokid].joystick != None:
					neue_lokid -= 1
				if self.regler[neue_lokid].joystick == None:
					self.lok_wechseln(lokid, neue_lokid, joystick)
			return True # Wenn nichts zurückgegeben wird, wird der gobject-scroll-thread automatisch beendet

	
	def set_auto_scroll(self, richtung, joystick):
		if self.joysticks[joystick][2] == richtung: # wenn immer noch die gleiche joyhat-richtung gedrückt ist
			GObject.timeout_add(JOYSTICK_SCROLL_REPEAT_TIME, self.scrollen, richtung, joystick)
		return False
	
	def quit(self):
		self.running = False

class GeschwindigkeitsThread():
	def __init__(self, joystickliste, loks, regler, achse):
		self.joysticks = joystickliste
		self.loks = loks
		self.reglerliste = regler
		self.achse = achse
		
	def go(self):
		for joystick_lok in self.joysticks:
			joystick = joystick_lok[0]
			lokid = joystick_lok[1]				
			ausschlag_vertikal = joystick.get_axis(self.achse)
			self.loks[lokid].joystick_beschleunigung(ausschlag_vertikal, self.reglerliste)
		return True

