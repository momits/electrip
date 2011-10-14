#!/usr/bin/env python
# -*- coding: UTF 8 -*-
# this is ELECTRIP VERSION 1.5.0

# Import von Modulen
try:
	import cPickle as pickle
	import time
	import gtk
	import socket
	import Joystick.JoystickKonsoleHP as joystick_konsole
	from Lok import Lok
	print "ELECTRIP-Steuerung: Importe erfolgreich"
except:
	print "ELECTRIP-Steuerung: Es konnten nicht alle Module importiert werden"
		
class Fenster(gtk.Window):
	def __init__(self, titel, config_fenster):
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		self.connect("delete-event", self.delete_event)
		self.grundbox = Grundbox() # Grundbox erzeugen
		self.add(self.grundbox)
		self.set_title(titel)
		self.show()
		self.config_fenster = config_fenster
		
		speicher_dict = self.config_fenster.grundbox.get_speicherdict()
		loks = speicher_dict["Loks"]
		server_dict = speicher_dict["Server"]
		joy_dict = speicher_dict["Joystick"]
				
		for lok in loks:
				i = 0
				for funktion in lok.funktionen:
					funktion["Nr"] = i
					i += 1
		try:
			self.socket_init(server_dict["Host"], int(server_dict["Port"]), loks)
			self.anzahl_loks = len(loks)
			self.hbox_mitte = HBoxMitte(self.anzahl_loks) # HBox für Regler erzeugen
			self.hbox_unten = HBoxUnten(self.socket) # HBox für Notstop erzeugen
			self.konfiguration_button = KonfigurationButton(self.config_fenster)
			self.grundbox.pack_start(self.konfiguration_button)
			self.grundbox.pack_start(self.hbox_mitte)
			self.grundbox.pack_start(self.hbox_unten, False, False)

			max_funktionsbuttons = 0
			for lok in loks:
				if len(lok.funktionen) > max_funktionsbuttons:
					max_funktionsbuttons = len(lok.funktionen)
			
			self.regler = []
			for i in range(self.anzahl_loks): # Alle Regler hinzufügen
				self.regler.append(Regler(self.socket, loks[i], max_funktionsbuttons))
				self.hbox_mitte.pack_start(self.regler[i])
			
			self.joystick_konsole = joystick_konsole.JoystickKonsole(loks, self.regler, self.hbox_unten.Notstopbutton, joy_dict)
			self.show()
		except:
			self.destroy()
			self.config_fenster.show()
			print "Das Steuerfenster konnte nicht geöffnet werden, überprüfen Sie die Einstellungen (Host, Port ...). Ist der SRCP-Server am Laufen?"
			print
		
	def delete_event(self, window=None, event=None, show_config_fenster=True):
		try:
			self.joystick_konsole.quit()
			self.socket.send("TERM 1 POWER\n")
			self.socket.send("TERM 0 SESSION\n")
		except:
			pass
		self.destroy()
		if show_config_fenster:
			self.config_fenster.show()
		print "Steuerung geschlossen."
	
	def socket_init(self, host, port, loks):
		print
		# Socket-Verbindung herstellen
		self.socket = socket.create_connection((host, port))
		#-------- Handshake ----------
		print "Socketverbindung aktiv mit:"
		print self.socket.recv(4096)
		self.socket.send("SET CONNECTIONMODE SRCP COMMAND\n")
		print "Connectionmode 'Command' wird angefordert:"
		print self.socket.recv(4096)
		self.socket.send('GO\n')
		
		go_daten = self.socket.recv(4096)
		go_daten_liste = go_daten.split()
		self.session_id = go_daten_liste[len(go_daten_liste) - 1]
		print "Session ID:"
		print self.session_id
		print
		print "Von ELECTRIP aus kanns losgehen, was sagt der Server?"
		print go_daten
		
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

class KonfigurationButton(gtk.ToggleButton):
	def __init__(self, config_fenster):
		gtk.ToggleButton.__init__(self, "Konfiguration")
		self.connect("clicked", self.clicked, config_fenster)
		self.config_fenster_visible = False
		self.show()
	
	def clicked(self, button, config_fenster):
		if not self.config_fenster_visible:
			self.toggled()
			config_fenster.show()
			self.config_fenster_visible = True
		else:
			self.toggled()
			config_fenster.hide()
			self.config_fenster_visible = False
			
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


#if __name__ == "__main__":
#	ELECTRIP = Fenster("ELECTRIP 1.4.0", None)
