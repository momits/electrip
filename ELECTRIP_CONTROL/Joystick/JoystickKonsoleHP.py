#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# Versuchen, Module einzubinden
try:
	import pygtk
	import gtk
	import pygame
	from pygame.locals import *
	import time
	import threading
except:
	print "Es konnten nicht alle Module geladen werden."

class JoystickKonsole():
	def __init__(self, loks, regler, notstopbutton):
		pygame.init()
				
		self.AmLaufen = True # Status setzen
		pygame.joystick.init() # Joystick Modul initialisieren
		
		self.joysticks = []
		for id in range(pygame.joystick.get_count()):
			if not len(self.joysticks) == len(regler):
				self.joysticks.append([pygame.joystick.Joystick(id), id]) # Liste mit Joystickobjekten erstellen Format: [joystick, zugehörige lok]
			else:
				print "Joystick '" + pygame.joystick.Joystick(id).get_name() + "' wurde ignoriert, da ", pygame.joystick.get_count(), " Joysticks zuviel für ", len(regler), " Loks sind."
		
		print "Erkannte Joysticks:", len(self.joysticks)
		print
		
		print "Initialisierung:"
		for joystick_lok in self.joysticks: # Daten der angeschlossenen Joysticks auslesen
			joystick = joystick_lok[0]
			print "-------- " , joystick.get_id() , ". --------"
			if not joystick.get_name() == "ST LIS3LV02DL Accelerometer": # Eingebauten Beschleunigungssensor ignorieren
				joystick.init() # Joystick initialisieren
				print joystick.get_name()
				print "Anzahl Achsen:", joystick.get_numaxes()
				print "Anzahl Knöpfe:", joystick.get_numbuttons()
			else:
				self.joysticks.remove(joystick_lok)
		
		self.joy_thread = JoystickThread(self.joysticks, loks, regler, notstopbutton)
		self.joy_thread.start()
		self.geschw_thread = GeschwindigkeitsThread(self.joysticks, loks, regler)
		self.geschw_thread.start()
	
	def quit(self):
		print "Stoppe Threads ..."
		self.joy_thread.quit()
		self.geschw_thread.quit()
		pygame.event.post(pygame.event.Event(MOUSEBUTTONDOWN, {"pos": 0, "button": 0}))

class JoystickThread(threading.Thread):
	def __init__(self, joystickliste, loks, regler, notstopbutton):
		threading.Thread.__init__(self)
		self.farbliste = ["#319C45", "#4189C0", "#E360EA", "#E8353C", "#000000", "#EEBB4B", "#993719", "#7F7F7F", "#1D5200"]
		self.joysticks = joystickliste
		self.loks = loks
		self.regler = regler
		self.notstopbutton = notstopbutton
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
						self.regler[lokid].funktionsbox.button[funktion["Nr"]].clicked()
						konfiguriert = True
				if event.button == 10:
					self.regler[lokid].richtungswender.clicked()
				elif event.button == 9:
					self.notstopbutton.clicked()
				elif not konfiguriert:
					print "Nicht konfigurierter Button wurde gedrückt."
			if event.type == JOYHATMOTION:
				richtung = event.value
				lokid = self.joysticks[event.joy][1]
				joyid = self.joysticks[event.joy][0].get_id()
				if richtung[0] == 1:
					neue_lokid = lokid
					while neue_lokid < len(self.loks)-1 and self.regler[neue_lokid].joystick != None:
						neue_lokid += 1
					if self.regler[neue_lokid].joystick == None:
						self.regler[lokid].lokschild.remove_color()
						self.regler[lokid].joystick = None
						self.regler[neue_lokid].lokschild.set_color(self.farbliste[joyid])
						self.regler[neue_lokid].joystick = self.joysticks[event.joy][0]
						lokid = neue_lokid
				if richtung[0] == -1 and lokid > 0:
					neue_lokid = lokid
					while neue_lokid > 0 and self.regler[neue_lokid].joystick != None:
						neue_lokid -= 1
					if self.regler[neue_lokid].joystick == None:
						self.regler[lokid].lokschild.remove_color()
						self.regler[lokid].joystick = None
						self.regler[neue_lokid].lokschild.set_color(self.farbliste[joyid])
						self.regler[neue_lokid].joystick = self.joysticks[event.joy][0]
						lokid = neue_lokid
				print "Joystick hat zu Lok ", lokid, "gewechselt."
				self.joysticks[event.joy][1] = lokid
		
	def quit(self):
		self.running = False

class GeschwindigkeitsThread(threading.Thread):
	def __init__(self, joystickliste, loks, regler):
		threading.Thread.__init__(self)
		self.joysticks = joystickliste
		self.loks = loks
		self.reglerliste = regler
		self.running = True
		
	def run(self):
		while self.running:
			for joystick_lok in self.joysticks:
				joystick = joystick_lok[0]
				lokid = joystick_lok[1]				
				if joystick.get_numaxes >= 4:
					ausschlag_vertikal = joystick.get_axis(1)
					ausschlag_horizontal = joystick.get_axis(3)
				elif joystick.get_numaxes >= 2:
					ausschlag_vertikal = joystick.get_axis(0)
					ausschlag_horizontal = joystick.get_axis(1)
				self.loks[lokid].joystick_beschleunigung(ausschlag_vertikal, self.reglerliste)
			while gtk.events_pending():
				gtk.main_iteration(False)
			time.sleep(0.1)
			
	def quit(self):
		self.running = False

