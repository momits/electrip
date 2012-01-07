#!/usr/bin/env python
# -*- coding: UTF 8 -*-
# this is ELECTRIP VERSION 1.6.1

# Import von Modulen

import gtk
import socket
import Joystick.JoystickKonsole2 as joystick_konsole
from Lok import Lok
from LockedPrint import *
import pango
import glib

		
class Fenster(gtk.Window):
	def __init__(self, titel, config_fenster):
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		config_fenster.control_window_is_alive = True
		self.connect("delete-event", self.delete_event)
		self.set_title(titel)
		self.config_fenster = config_fenster
		self.is_fullscreen = False
		
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
			
			self.scrolled_window = ScrolledWindow(self.socket, loks, self) # ScrolledWindow und darin HBox für Regler erzeugen
			
			self.notstop_button = Notstopbutton(self.socket) # HBox für Notstop erzeugen
			self.konfiguration_button = KonfigurationButton(self, self.config_fenster)
			self.fullscreen_button = FullscreenButton(self)
			
			self.hbox_oben = gtk.HBox()
			self.hbox_oben.pack_start(self.konfiguration_button)
			self.hbox_oben.pack_start(self.fullscreen_button, False, False)
			
			self.grundbox = gtk.VBox() # Grundbox erzeugen
			self.grundbox.pack_start(self.hbox_oben, False, False)
			self.grundbox.pack_start(self.scrolled_window, True, True)
			self.grundbox.pack_start(self.notstop_button, False, False)
			self.add(self.grundbox)
			
			self.joystick_konsole = joystick_konsole.JoystickKonsole(loks, self.scrolled_window.hbox_mitte.regler, self.notstop_button, joy_dict)
			self.maximize()
			self.show_all()			
			
		except ValueError:
			self.destroy()
			self.config_fenster.show_all()
			self.config_fenster.error("Der Server-Port ist nicht korrekt.")
		except socket.error:
			self.destroy()
			self.config_fenster.show_all()
			self.config_fenster.error("Es konnte keine Verbindung zum SRCP-Server aufgebaut werden.\nÜberprüfen Sie die Server-Einstellungen (Host, Port ...).\nIst der SRCP-Server am Laufen?")
		except NameError:
			locked_print("Konnte pygame-Threads nicht starten, Joysticks werden folglich nicht erkannt.")
		
	def delete_event(self, window=None, event=None, show_config_fenster=True):
		try:
			self.joystick_konsole.quit()
			self.socket_thread.quit()
			self.socket.send("TERM 1 POWER\n")
			self.socket.send("TERM 0 SESSION\n")
		except:
			pass
		self.destroy()
		self.config_fenster.control_window_is_alive = False
		if show_config_fenster:
			self.config_fenster.show()
		locked_print("Steuerung geschlossen.")
	
	def socket_init(self, host, port, loks):
		# Socket-Verbindung herstellen
		self.socket = socket.create_connection((host, port))
		#-------- Handshake ----------
		locked_print("Socketverbindung aktiv mit:")
		locked_print(self.socket.recv(4096))
		self.socket.send("SET CONNECTIONMODE SRCP COMMAND\n")
		locked_print("Connectionmode 'Command' wird angefordert:")
		locked_print(self.socket.recv(4096))
		self.socket.send('GO\n')
		
		go_daten = self.socket.recv(4096)
		go_daten_liste = go_daten.split()
		self.session_id = go_daten_liste[len(go_daten_liste) - 1]
		locked_print("Session ID:")
		locked_print(self.session_id)
		locked_print("\nVon ELECTRIP aus kanns losgehen, was sagt der Server?")
		locked_print(go_daten)
		
		# -------- Stromversorgung auf Bus 1 initiieren ---------
		locked_print("Strom wird angeschaltet")
		self.socket.send("INIT 1 POWER\n")
		locked_print(self.socket.recv(4096))
		# ---------- Loks initialisieren -------------
		for lok in loks:
			if lok.protokoll == "M 1" or "M 2" or "N 1" or "N 2":
				text = "INIT 1 GL " + str(lok.adresse) + " " + str(lok.protokoll) + " " + str(lok.fahrstufen) + " " + str(lok.anzahl_funktionen) + "\n"
				locked_print(text)
				self.socket.send(text)
				locked_print(self.socket.recv(4096))
			else:
				locked_print("Lok", lok.name, "verwendet ein nicht unterstütztes Digitalprotokoll.")

		self.socket_thread = SocketRecvThread(self.socket) # Nach dem Handshake und Lok-Init wird der Receive in einen separaten Thread verlegt -> keine GUI-Blockierungen möglich
		self.socket_thread.start()

class ScrolledWindow(gtk.ScrolledWindow):
	def __init__(self, socket, loks, fenster):
		gtk.ScrolledWindow.__init__(self)
		self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.hbox_mitte = HBoxMitte(socket, loks, fenster, self)
		self.add_with_viewport(self.hbox_mitte)
		locked_print("ScrolledWindow original:", self)
		
class HBoxMitte(gtk.HBox):
	def __init__(self, socket, loks, fenster, scrolled_window):
		gtk.HBox.__init__(self)
		self.regler = []
		for i in range(len(loks)): # Alle Regler hinzufügen
			self.regler.append(Regler(socket, loks[i], scrolled_window))
			self.pack_start(self.regler[i])
		self.connect("realize", self.realized, fenster, loks)
				
	def realized(self, hbox, fenster, loks):
		width, height = self.size_request()
		fenster.resize(width + 100, height + 100)
		
		search_pending = True
		max_funktionsbuttons = 0
		for regler in self.regler:
			if len(regler.lok.funktionen) > max_funktionsbuttons:
				max_funktionsbuttons = len(regler.lok.funktionen)
				if search_pending:
					button_width, button_height = regler.funktionsbox.buttons[0].size_request()
					search_pending = False
		for regler in self.regler:
			regler.funktionsbox.set_size_request(-1, max_funktionsbuttons * button_height)

class Regler(gtk.VBox):
	def __init__(self, socket, lok, scrolled_window):
		gtk.VBox.__init__(self)
		self.lok = lok
		self.joystick = None
		self.lokbild = Lokbild(lok.bild)
		self.geschwindigkeitsregler = Geschwindigkeitsregler(lok, socket)
		self.lokschild = Lokschild(lok)
		self.richtungswender = Richtungswender(lok, socket, self.geschwindigkeitsregler)
		self.funktionsbox = Funktionsbox(lok, lok.funktionen, socket)
		self.scrolled_window = scrolled_window
		
		self.pack_start(self.lokbild, False, False)
		self.pack_start(self.geschwindigkeitsregler, True, True)
		self.pack_start(self.lokschild, False, False)
		self.pack_start(self.richtungswender, False, False)
		self.pack_start(self.funktionsbox, False, False, 10)
		
	def set_focus(self): # Regler im ScrolledWindow sichtbar machen
		adjust = self.scrolled_window.get_hadjustment()
		adjust.clamp_page(self.allocation.x, self.allocation.x + self.allocation.width)

class KonfigurationButton(gtk.ToggleButton):
	def __init__(self, fenster, config_fenster):
		gtk.ToggleButton.__init__(self, "Konfiguration")
		self.set_size_request(-1, 30)
		self.connect("clicked", self.clicked, fenster, config_fenster)
	
	def clicked(self, button, fenster, config_fenster):
		if config_fenster.get_property("visible"):
			self.toggled()
			config_fenster.hide()
			if fenster.is_fullscreen:
				fenster.fullscreen()
		else:
			self.toggled()
			if fenster.is_fullscreen:
				fenster.unfullscreen()
			config_fenster.show()

class FullscreenButton(gtk.ToggleButton):
	def __init__(self, fenster):
		gtk.ToggleButton.__init__(self)
		icon = gtk.Image()
		icon.set_from_stock(gtk.STOCK_FULLSCREEN, gtk.ICON_SIZE_BUTTON)
		label = gtk.Label("Vollbild")
		hbox = gtk.HBox(False, 5)
		hbox.pack_start(label)
		hbox.pack_start(icon)
		self.add(hbox)
		self.set_size_request(-1, 30)
		self.connect("clicked", self.clicked, fenster)
	
	def clicked(self, button, fenster):
		if fenster.is_fullscreen:
			self.toggled()
			fenster.unfullscreen()
			fenster.is_fullscreen = False
		else:
			self.toggled()
			fenster.fullscreen()
			fenster.is_fullscreen = True
			
class Lokbild(gtk.Image):
	def __init__(self, pfad):
		gtk.Image.__init__(self)
		self.set_size_request(110, 85)
		if pfad == None:
			self.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_BUTTON)
		else:
			try:
				pixbuf= gtk.gdk.pixbuf_new_from_file(pfad)
				small_pixbuf = pixbuf.scale_simple(110 , 85, gtk.gdk.INTERP_BILINEAR)
				self.set_from_pixbuf(small_pixbuf)
			except glib.GError:
				self.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_BUTTON)
				locked_print("Dateipfad" + pfad + "für Lokbild ist ungültig.")

	def aendern(self, pfad):
		self.set_from_file(pfad)

class Geschwindigkeitsregler(gtk.VScale):
	def __init__(self, lok, socket):
		self.fahrstufen = gtk.Adjustment(0, 0, lok.fahrstufen, 1, 0, 0)
		gtk.VScale.__init__(self, self.fahrstufen)
		self.connect("value-changed", self.geschw_aenderung, lok, socket)
		self.set_inverted(True)
		self.set_digits(1)
		self.set_value_pos(gtk.POS_BOTTOM)

	def geschw_aenderung(self, scale, lok, socket):
		geschw_aktuell = self.get_value()
		locked_print("Lok", lok.name, "fährt jetzt", lok.geschwindigkeit, ", das entspricht", int(lok.geschwindigkeit), "Fahrstufen.")
		lok.geschwindigkeit = geschw_aktuell
		if int(lok.geschwindigkeit) != lok.letzte_gesendete_geschwindigkeit:
			lok.an_server_senden(socket)

class Lokschild(gtk.Label):
	def __init__(self, lok):
		self.text = lok.name
		gtk.Label.__init__(self, self.text)
		self.set_ellipsize(pango.ELLIPSIZE_END)
	
	def set_color(self, color):
		markup = "<span foreground='" + color + "'>" + "<b>" + self.text + "</b>" + "</span>"
		self.set_markup(markup)
	
	def remove_color(self):
		self.set_markup(self.text)
	
class Richtungswender(gtk.Button):
	def __init__(self, lok, socket, scale):
		gtk.Button.__init__(self)
		self.set_size_request(-1, 30)
		self.pfeil_hoch = gtk.Arrow(gtk.ARROW_UP, gtk.SHADOW_NONE)
		self.pfeil_runter = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_NONE)
		self.zeige_richtungspfeil(lok.richtung)
		self.connect("clicked", self.richtungswechsel, lok, socket, scale)

	def richtungswechsel(self, button, lok, socket, scale):
		lok.richtung = not lok.richtung
		locked_print("\nLok", lok.name, "hat die Richtung gewechselt und fährt nun", lok.richtung)
		
		if lok.geschwindigkeit == 0:
			lok.an_server_senden(socket)
		else:
			scale.set_value(0)
		
		self.zeige_richtungspfeil(lok.richtung)
	
	def zeige_richtungspfeil(self, richtung):
		if richtung:
			self.set_image(self.pfeil_hoch)
		else:
			self.set_image(self.pfeil_runter)

class Funktionsbutton(gtk.ToggleButton):
	def __init__(self, lok, funktionsname, wert, sende_nr, nr, socket):
		self.text = funktionsname
		gtk.ToggleButton.__init__(self, self.text)
		self.connect("clicked", self.funktion_umschalten, lok, nr, socket)
		self.child_label = self.get_child()
		self.child_label.set_ellipsize(pango.ELLIPSIZE_END)
		self.lok = lok
		self.sende_nr = sende_nr
		self.wert = not wert
		self.nr = nr

		self.funktion_umschalten(None, self.lok, self.nr, socket)

	def funktion_umschalten(self, button, lok, nr, socket):
		self.wert = not self.wert
		if self.wert:
			lok.funktionen[nr]["Wert"] = True
			locked_print("Lok", lok.name, "hat die Funktion", self.text, "angeschaltet.")
			lok.an_server_senden(socket)
		else:
			lok.funktionen[nr]["Wert"] = False
			locked_print("Lok", lok.name, "hat die Funktion", self.text, "ausgeschaltet.")
			lok.an_server_senden(socket)
		self.toggled()

class Funktionsbox(gtk.VButtonBox):
	def __init__(self, lok,funktionen, socket):
		gtk.VButtonBox.__init__(self)
		self.set_layout(gtk.BUTTONBOX_START)
		self.buttons = []
		for funktion in lok.funktionen:
			neuer_funktionsbutton = Funktionsbutton(lok, funktion["Name"], funktion["Wert"], funktion["SendeNr"], funktion["Nr"], socket)
			self.buttons.append(neuer_funktionsbutton)
			self.pack_start(neuer_funktionsbutton)

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
	
	def set_strom(self, *args):
		self.strom_an = not self.strom_an
		if self.strom_an:
			self.set_farbe(self.hellgrau, self.dunkelgrau)
			self.socket.send("SET 1 POWER ON\n")
			locked_print("\nStrom angeschaltet")
		else:
			self.set_farbe(self.rot, self.dunkelgrau)
			self.socket.send("SET 1 POWER OFF\n")
			locked_print("\nNotstop eingeleitet")
		
	def set_farbe(self, hintergrund, vordergrund):
		self.modify_bg(gtk.STATE_NORMAL, hintergrund)
		self.child_label.modify_fg(gtk.STATE_NORMAL, vordergrund)
		
		self.modify_bg(gtk.STATE_ACTIVE, hintergrund)
		self.child_label.modify_fg(gtk.STATE_ACTIVE, vordergrund)
		
		self.modify_bg(gtk.STATE_PRELIGHT, hintergrund)
		self.child_label.modify_fg(gtk.STATE_PRELIGHT, vordergrund)
		
		self.modify_bg(gtk.STATE_SELECTED, hintergrund)
		self.child_label.modify_fg(gtk.STATE_SELECTED, vordergrund)
