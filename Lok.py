#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from LockedPrint import locked_print

class Lok():
	def __init__(self, id, name, adresse, protokoll, fahrstufen, beschleunigungszeit, fahrtrichtung, bildpfad, funktionen, server_bus):
		self.id = id
		self.name = name
		self.adresse = adresse
		self.protokoll = protokoll
		self.fahrstufen = fahrstufen
		self.beschleunigungszeit = beschleunigungszeit
		self.richtung = fahrtrichtung
		self.bild = bildpfad
		self.funktionen = funktionen
		self.geschwindigkeit = 0.0
		self.letzte_gesendete_geschwindigkeit = 0
		self.anzahl_funktionen = 0
		for funktion in self.funktionen:
			if funktion["SendeNr"] + 1 > self.anzahl_funktionen:
				self.anzahl_funktionen = funktion["SendeNr"] + 1 # Ermittle höchste SendeNr, für SRCP-Befehle
		self.server_bus = str(server_bus)

	def an_server_senden(self, socket):
		self.letzte_gesendete_geschwindigkeit = int(self.geschwindigkeit)
		geschaltet = []
		for i in range(self.anzahl_funktionen):
			geschaltet.append(False)
		for funktion in self.funktionen:
			if funktion["Wert"]:
				geschaltet[funktion["SendeNr"]] = True
		funktionen = " ".join(str(int(n)) for n in geschaltet)
		sendetext = "SET " + self.server_bus + " GL " + str(self.adresse) + " " + str(int(self.richtung)) + " " + str(int(self.geschwindigkeit)) + " " + str(self.fahrstufen) + " " + funktionen + "\n"
		
		locked_print("\n" + sendetext)
		socket.send(sendetext)
	
	def joystick_beschleunigung(self, wert, regler):
		self.geschwindigkeit = self.geschwindigkeit - wert * (0.1 / regler[self.id].lok.beschleunigungszeit * self.fahrstufen)
		if self.geschwindigkeit < 0:
			self.geschwindigkeit = 0
		if self.geschwindigkeit > self.fahrstufen:
			self.geschwindigkeit = self.fahrstufen
		regler[self.id].geschwindigkeitsregler.set_value(self.geschwindigkeit)
