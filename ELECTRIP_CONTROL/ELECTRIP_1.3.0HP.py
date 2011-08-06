#!/usr/bin/env python
# -*- coding: UTF 8 -*-

# Import von Modulen
try:
	import cPickle as pickle
	import sys
	import time
	import gtk
	import socket
	import Joystick.JoystickKonsoleHP as joystick_konsole
	print "Importe erfolgreich"
except:
	print "Es konnten nicht alle Module importiert werden"

class Lok():
	def __init__(self, id, name, adresse, protokoll, fahrstufen, beschleunigungszeit, fahrtrichtung, bildpfad, funktionen):
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
				self.anzahl_funktionen = funktion["SendeNr"] + 1

	def an_server_senden(self, socket):
		self.letzte_gesendete_geschwindigkeit = int(self.geschwindigkeit)
		geschaltet = []
		for i in range(self.anzahl_funktionen):
			geschaltet.append(False)
		for funktion in self.funktionen:
			if funktion["Wert"]:
				geschaltet[funktion["SendeNr"]] = True
		funktionen = " ".join(str(int(n)) for n in geschaltet)
		sendetext = "SET 1 GL " + str(self.adresse) + " " + str(int(self.richtung)) + " " + str(int(self.geschwindigkeit)) + " " + str(self.fahrstufen) + " " + funktionen + "\n"
		print
		print sendetext
		socket.send(sendetext)
		print socket.recv(4096)
	
	def joystick_beschleunigung(self, wert, regler):
		self.geschwindigkeit = self.geschwindigkeit - wert * (0.1 / regler[self.id].lok.beschleunigungszeit * self.fahrstufen)
		if self.geschwindigkeit < 0:
			self.geschwindigkeit = 0
		if self.geschwindigkeit > self.fahrstufen:
			self.geschwindigkeit = self.fahrstufen
		regler[self.id].geschwindigkeitsregler.set_value(self.geschwindigkeit)
		
class Fenster(gtk.Window):
	def __init__(self, host, port, titel, loks):			
		self.socket_init(host, port, loks)
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		self.anzahl_loks = len(loks)
		self.set_title(titel)
		self.connect("delete-event", self.delete_event)
		
		self.grundbox = Grundbox() # Grundbox erzeugen
		self.hbox_mitte = HBoxMitte(self.anzahl_loks) # HBox für Regler erzeugen
		self.hbox_unten = HBoxUnten(self.socket) # HBox für Notstop erzeugen
		self.grundbox.pack_start(self.hbox_mitte)
		self.grundbox.pack_start(self.hbox_unten, False, False)
		self.add(self.grundbox)
		
		max_funktionsbuttons = 0
		for lok in loks:
			if len(lok.funktionen) > max_funktionsbuttons:
				max_funktionsbuttons = len(lok.funktionen)
		
		self.regler = []
		for i in range(self.anzahl_loks): # Alle Regler hinzufügen
			self.regler.append(Regler(self.socket, loks[i], max_funktionsbuttons))
			self.hbox_mitte.pack_start(self.regler[i])
		
		self.show()
		
	def delete_event(self, *args):
		self.socket.send("TERM 1 POWER\n")
		self.socket.send("TERM 0 SESSION\n")
		self.joystick_konsole.quit()
		print "Das Programm wurde beendet."
		
	def schneller_exit(self):
		print "Das Programm konnte nicht gestartet werden."
		sys.exit()
	
	def socket_init(self, host, port, loks):
		# Socket-Verbindung herstellen
		try:
			self.socket = socket.create_connection((host, port))
		except:
			print "Socket Verbindung gescheitert. Host und Port überprüfen!"
			self.schneller_exit()
		#-------- Handshake ----------
		print "Socketverbindung aktiv mit:", self.socket.recv(4096)
		self.socket.send("SET CONNECTIONMODE SRCP COMMAND\n")
		print "Connectionmode 'Command' wird angefordert:", self.socket.recv(4096)
		self.socket.send('GO\n')
		
		go_daten = self.socket.recv(4096)
		go_daten_liste = go_daten.split()
		self.session_id = go_daten_liste[len(go_daten_liste) - 1]
		print "Session ID:", self.session_id
		print "Von PyControl aus kanns losgehen, was sagt der Server?", go_daten
		
		# -------- Stromversorgung auf Bus 1 initiieren ---------
		self.socket.send("INIT 1 POWER\n")
		print self.socket.recv(4096)
		# ---------- Loks initialisieren -------------
		for lok in loks:
			if lok.protokoll == "M 1" or "M 2" or "N 1" or "N 2":
				text = "INIT 1 GL " + str(lok.adresse) + " " + str(lok.protokoll) + " " + str(lok.fahrstufen) + " " + str(lok.anzahl_funktionen) + "\n"
				print text
				self.socket.send(text)
				print self.socket.recv(4096)
			else:
				print "Lok", lok.name, "verwendet ein nicht unterstütztes Digitalprotokoll."


class Grundbox(gtk.VBox):
	def __init__(self):
		gtk.VBox.__init__(self, False, 0)
		self.show()

class HBoxMitte(gtk.HBox):
	def __init__(self, anzahl_loks):
		gtk.HBox.__init__(self, False, 0)
		self.set_optimale_breite(anzahl_loks)
		self.show()
		
	def set_manuelle_breite(breite):
		self.set_size_request(breite, -1)
	
	def set_optimale_breite(self, anzahl_loks):
		self.set_size_request(anzahl_loks * 115, -1)

class HBoxUnten(gtk.HBox):
	def __init__(self, socket):
		gtk.HBox.__init__(self, False, 0)
		self.Notstopbutton = Notstopbutton(socket)
		self.pack_start(self.Notstopbutton)
		self.show()
	
class Regler(gtk.VBox):
	def __init__(self, socket, lok, max_funktionsbuttons):
		gtk.VBox.__init__(self, False, 0)
		self.lok = lok
		self.joystick = None
		self.lokbild = Lokbild(lok.bild)
		self.geschwindigkeitsregler = Geschwindigkeitsregler(lok, socket)
		self.lokschild = Lokschild(lok)
		self.richtungswender = Richtungswender(lok, socket, self.geschwindigkeitsregler)
		self.funktionsbox = Funktionsbox(lok, max_funktionsbuttons, lok.funktionen, socket)
		self.pack_start(self.lokbild)
		self.pack_start(self.geschwindigkeitsregler)
		self.pack_start(self.lokschild)
		self.pack_start(self.richtungswender)
		self.pack_start(self.funktionsbox, True, True, 10)
		self.show()
			
				
class Lokbild(gtk.Image):
	def __init__(self, pfad):
		gtk.Image.__init__(self)
		self.set_size_request(-1, 90)
		if pfad == None:
			self.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_BUTTON)
		else:
			self.set_from_file(pfad)
		self.show()

	def aendern(self, pfad):
		self.set_from_file(pfad)


class Geschwindigkeitsregler(gtk.VScale):
	def __init__(self, lok, socket):
		self.fahrstufen = gtk.Adjustment(0, 0, lok.fahrstufen, 1, 0, 0)
		gtk.VScale.__init__(self, self.fahrstufen)
		self.connect("value-changed", self.geschw_aenderung, lok, socket)
		self.set_size_request(-1, 300)
		self.set_inverted(True)
		self.set_digits(1)
		self.set_value_pos(gtk.POS_BOTTOM)
		self.show()

	def geschw_aenderung(self, scale, lok, socket):
		geschw_aktuell = self.get_value()
		print "Lok", lok.name, "fährt jetzt", lok.geschwindigkeit, ", das entspricht", int(lok.geschwindigkeit), "Fahrstufen."
		lok.geschwindigkeit = geschw_aktuell
		if int(lok.geschwindigkeit) != lok.letzte_gesendete_geschwindigkeit:
			lok.an_server_senden(socket)

class Lokschild(gtk.Label):
	def __init__(self, lok):
		self.text = lok.name
		gtk.Label.__init__(self, self.text)
		self.show()
	
	def set_color(self, color):
		markup = "<span foreground='" + color + "'>" + "<b>" + self.text + "</b>" + "</span>"
		self.set_markup(markup)
	
	def remove_color(self):
		self.set_markup(self.text)
	
class Richtungswender(gtk.Button):
	def __init__(self, lok, socket, scale):
		gtk.Button.__init__(self)
		self.pfeil_hoch = self.neuer_pfeil(True)
		self.pfeil_runter = self.neuer_pfeil(False)
		self.zeige_richtungspfeil(lok.richtung)
		self.connect("clicked", self.richtungswechsel, lok, socket, scale)
		self.show()
	
	def neuer_pfeil(self, pfeil_hoch = True):
		if pfeil_hoch:
			neuer_richtungspfeil = gtk.Arrow(gtk.ARROW_UP, gtk.SHADOW_NONE)
		else:
			neuer_richtungspfeil = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_NONE)
		return neuer_richtungspfeil
	
	def richtungswechsel(self, button, lok, socket, scale):
		lok.richtung = not lok.richtung
		print "Lok", lok.name, "hat die Richtung gewechselt und fährt nun", lok.richtung
		
		if lok.geschwindigkeit == 0:
			lok.an_server_senden(socket)
		else:
			scale.set_value(0)
		print
		self.zeige_richtungspfeil(lok.richtung)
	
	def zeige_richtungspfeil(self, richtung):
		if richtung:
			self.set_image(self.pfeil_hoch)
		else:
			self.set_image(self.pfeil_runter)

class Funktionsbutton(gtk.Button):
	def __init__(self, lok, funktionsname, wert, sende_nr, nr, socket):
		self.text = funktionsname
		gtk.Button.__init__(self, self.text)
		self.connect("clicked", self.funktion_umschalten, lok, nr, socket)
		self.child_label = self.get_child()
		self.lok = lok
		self.sende_nr = sende_nr
		self.wert = wert
		self.nr = nr
		
		self.hellgrau = gtk.gdk.Color(45600, 45600, 45600)
		self.dunkelgrau = gtk.gdk.Color(20500, 20500, 20500)
		self.fastweiss = gtk.gdk.Color(50000, 50000, 56000)
		
		self.wert = not self.wert
		self.funktion_umschalten(None, self.lok, self.nr, socket)
		
		self.show()

	def funktion_umschalten(self, button, lok, nr, socket):
		self.wert = not self.wert
		if self.wert:
			self.set_farbe(self.dunkelgrau, self.fastweiss)
			lok.funktionen[nr]["Wert"] = True
			print "Lok", lok.name, "hat die Funktion", self.text, "angeschaltet."
			lok.an_server_senden(socket)
		else:
			self.set_farbe(self.hellgrau, self.dunkelgrau)
			lok.funktionen[nr]["Wert"] = False
			print "Lok", lok.name, "hat die Funktion", self.text, "ausgeschaltet."
			lok.an_server_senden(socket)
	
	def set_farbe(self, hintergrund, vordergrund):
		self.modify_bg(gtk.STATE_NORMAL, hintergrund)
		self.child_label.modify_fg(gtk.STATE_NORMAL, vordergrund)
		
		self.modify_bg(gtk.STATE_ACTIVE, hintergrund)
		self.child_label.modify_fg(gtk.STATE_ACTIVE, vordergrund)
		
		self.modify_bg(gtk.STATE_PRELIGHT, hintergrund)
		self.child_label.modify_fg(gtk.STATE_PRELIGHT, vordergrund)
		
		self.modify_bg(gtk.STATE_SELECTED, hintergrund)
		self.child_label.modify_fg(gtk.STATE_SELECTED, vordergrund)

class Funktionsbox(gtk.VButtonBox):
	def __init__(self, lok, max_funktionsbuttons, funktionen, socket):
		gtk.VButtonBox.__init__(self)
		self.button = []
		for funktion in lok.funktionen:
			neuer_funktionsbutton = Funktionsbutton(lok, funktion["Name"], funktion["Wert"], funktion["SendeNr"], funktion["Nr"], socket)
			self.button.append(neuer_funktionsbutton)
			self.pack_start(neuer_funktionsbutton)
		self.set_size_request(-1 , max_funktionsbuttons * 35)
		self.set_layout(gtk.BUTTONBOX_START)
		self.show()


class Notstopbutton(gtk.Button):
	def __init__(self, socket):
		gtk.Button.__init__(self, "Notstop")
		self.set_size_request(-1 , 65)
		self.socket = socket
		self.strom_an = False
		self.rot = gtk.gdk.Color(60000, 30000, 30000)
		self.hellgrau = gtk.gdk.Color(45600, 45600, 45600)
		self.dunkelgrau = gtk.gdk.Color(20500, 20500, 20500)
		self.child_label = self.get_child()
		self.connect("clicked", self.set_strom)
		self.set_strom()
		self.show()
	
	def set_strom(self, *args):
		self.strom_an = not self.strom_an
		if self.strom_an:
			self.set_farbe(self.hellgrau, self.dunkelgrau)
			self.socket.send("SET 1 POWER ON\n")
			print
			print "Strom angeschaltet"
			print self.socket.recv(4096)
		else:
			self.set_farbe(self.rot, self.dunkelgrau)
			self.socket.send("SET 1 POWER OFF\n")
			print
			print "Notstop eingeleitet"
			print self.socket.recv(4096)
		
	def set_farbe(self, hintergrund, vordergrund):
		self.modify_bg(gtk.STATE_NORMAL, hintergrund)
		self.child_label.modify_fg(gtk.STATE_NORMAL, vordergrund)
		
		self.modify_bg(gtk.STATE_ACTIVE, hintergrund)
		self.child_label.modify_fg(gtk.STATE_ACTIVE, vordergrund)
		
		self.modify_bg(gtk.STATE_PRELIGHT, hintergrund)
		self.child_label.modify_fg(gtk.STATE_PRELIGHT, vordergrund)
		
		self.modify_bg(gtk.STATE_SELECTED, hintergrund)
		self.child_label.modify_fg(gtk.STATE_SELECTED, vordergrund)

if __name__ == "__main__":
	loks = pickle.load(open("conf.elc"))
	for lok in loks:
			i = 0
			for funktion in lok.funktionen:
				funktion["Nr"] = i
				i += 1

	# Hier Daten für Socketverbindung eingeben: Fenster("adresse", port, ....)
	PyControl = Fenster("localhost", 4303, "ELECTRIP 1.2.2", loks)
	PyControl.joystick_konsole = joystick_konsole.JoystickKonsole(loks, PyControl.regler, PyControl.hbox_unten.Notstopbutton)
