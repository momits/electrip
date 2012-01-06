#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import glib
from LockedPrint import locked_print
try:
	import pygame
	from pygame.locals import * # Importiere Konstanten (JOYBUTTTONDOWN, ...) für kurze Namen
except ImportError:
	locked_print("PyGame ist nicht installiert, Joysticks können nicht verwendet werden.")

import threading

class JoystickKonsole():
	def __init__(self, loks, regler, notstopbutton, joy_dict):
			
		pygame.init()
				
		self.AmLaufen = True # Status setzen
		pygame.joystick.init() # Joystick Modul initialisieren
		
		self.joysticks = []
		for id in range(pygame.joystick.get_count()):
			if not len(self.joysticks) == len(regler):
				self.joysticks.append([pygame.joystick.Joystick(id), id]) # Liste mit Joystickobjekten erstellen Format: [joystick, zugehörige lok]
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
		
		self.joy_thread = JoystickThread(self.joysticks, loks, regler, notstopbutton, joy_dict["Notstop"], joy_dict["Richtungswender"], joy_dict["Fokus"])
		self.joy_thread.start()
		self.geschw_thread = GeschwindigkeitsThread(self.joysticks, loks, regler, joy_dict["Achse"])
		self.geschw_thread_id = glib.timeout_add(100, self.geschw_thread.go)
		
	
	def quit(self):
		locked_print("Stoppe Threads ...")
		self.joy_thread.quit()
		glib.source_remove(self.geschw_thread_id)
		pygame.event.post(pygame.event.Event(MOUSEBUTTONDOWN, {"pos": 0, "button": 0})) # Event posten, um joystick_thread zu beenden

class JoystickThread(threading.Thread):
	def __init__(self, joystickliste, loks, regler, notstopbutton, joy_button_notstop, joy_button_richtungswender, joy_button_set_focus):
		threading.Thread.__init__(self)
		self.farbliste = ["#319C45", "#4189C0", "#E360EA", "#E8353C", "#000000", "#EEBB4B", "#993719", "#7F7F7F", "#1D5200"]
		self.joysticks = joystickliste
		if len(self.joysticks) == 1:
			self.auto_focus = True
		else:
			self.auto_focus = False
		locked_print("Auto-Fokus:", self.auto_focus)
		self.loks = loks
		self.regler = regler
		self.notstopbutton = notstopbutton
		
		self.joy_button_notstop = joy_button_notstop
		self.joy_button_richtungswender = joy_button_richtungswender
		self.joy_button_set_focus = joy_button_set_focus
		
		for joystick_lok in self.joysticks:
			self.regler[joystick_lok[1]].lokschild.set_color(self.farbliste[joystick_lok[1]])
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
						glib.idle_add(self.regler[lokid].funktionsbox.buttons[funktion["Nr"]].clicked)
						konfiguriert = True
				if event.button == self.joy_button_richtungswender: # Gtk ist NICHT thread-safe, d.h. es können Probleme auftreten wenn von anderen threads Gtk-Objekte geändert werden
					glib.idle_add(self.regler[lokid].richtungswender.clicked) # Deshalb: glib.idle_add(Funktion, Parameter1, ...) -> Gtk-Hauptschleife führt Funktion mit Parametern aus, wenn sie Zeit hat
				elif event.button == self.joy_button_notstop:
					glib.idle_add(self.notstopbutton.clicked)
				elif event.button == self.joy_button_set_focus:
					glib.idle_add(self.regler[lokid].set_focus) # Lässt die Gtk-Hauptschleife die Funktion Regler.set_focus aufrufen, verhindert raise-conditions die zum crash führen können
				elif not konfiguriert:  # Ist Button nicht in Lokfunktionen oder Spezialbuttons, ist er nicht konfiguriert
					locked_print("Nicht konfigurierter Button wurde gedrückt.")
			if event.type == JOYBUTTONUP:
				lokid = self.joysticks[event.joy][1]
				for funktion in self.loks[lokid].funktionen:
					if event.button == funktion["Button"] and funktion["Taster"]:
						glib.idle_add(self.regler[lokid].funktionsbox.buttons[funktion["Nr"]].clicked)
			if event.type == JOYHATMOTION:
				richtung = event.value
				lokid = self.joysticks[event.joy][1]
				if richtung[0] == 1 and lokid < len(self.regler)-1: # wenn lokid = länge von self.regler muss nicht gewechselt werden
					neue_lokid = lokid
					while neue_lokid < len(self.loks)-1 and self.regler[neue_lokid].joystick != None:
						neue_lokid += 1 # Findet nächste freie Lok-ID
					if self.regler[neue_lokid].joystick == None: # Prüfen, ob Lok frei ist (falls alle Loks mit Joysticks besetzt sind)
						glib.idle_add(self.regler[lokid].lokschild.remove_color)
						self.regler[lokid].joystick = None
						glib.idle_add(self.regler[neue_lokid].lokschild.set_color, self.farbliste[event.joy])
						self.regler[neue_lokid].joystick = self.joysticks[event.joy][0]
						if self.auto_focus: # Wenn nur ein Joystick, dann diesen fokussieren
							glib.idle_add(self.regler[neue_lokid].set_focus) # Siehe oben
						lokid = neue_lokid
				if richtung[0] == -1 and lokid > 0: # wenn lokid = 0 muss nicht gewechselt werden
					neue_lokid = lokid
					while neue_lokid > 0 and self.regler[neue_lokid].joystick != None:
						neue_lokid -= 1
					if self.regler[neue_lokid].joystick == None:
						glib.idle_add(self.regler[lokid].lokschild.remove_color)
						self.regler[lokid].joystick = None
						glib.idle_add(self.regler[neue_lokid].lokschild.set_color, self.farbliste[event.joy])
						self.regler[neue_lokid].joystick = self.joysticks[event.joy][0]
						if self.auto_focus: # Wenn nur ein Joystick, dann diesen fokussieren
							glib.idle_add(self.regler[neue_lokid].set_focus) # Siehe oben
						lokid = neue_lokid
				locked_print("Joystick ", event.joy, " hat zu Lok ", lokid, "gewechselt.")
				self.joysticks[event.joy][1] = lokid
		
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

