#!/usr/bin/env python
# -*- coding: UTF 8 -*-
# this is ELECTRIP VERSION 2.0.1

# Import von Modulen

from gi.repository.GLib import GError
from gi.repository import Gtk, Pango, Gdk, GdkPixbuf
import socket
import Joystick.JoystickKonsole2 as joystick_konsole
from Lok import Lok
from Constants import *
from LockedPrint import *

		
class Fenster(Gtk.Window):
	def __init__(self, config_fenster):
		super(Fenster, self).__init__() #Gtk.WindowType.TOPLEVEL
		config_fenster.control_window_is_alive = True
		self.connect("delete-event", self.delete_event)
		self.set_title("ELECTRIP " + ELECTRIP_VERSION + " Steuerung - " + str(config_fenster.grundbox.verzeichnis))
		icon_list = [GdkPixbuf.Pixbuf.new_from_file(path) for path in ICON_PATH_LIST]
		self.set_icon_list(icon_list)
		self.config_fenster = config_fenster
		self.is_fullscreen = False
		
		speicher_dict = self.config_fenster.grundbox.get_speicherdict()
		loks = speicher_dict["Loks"]
		server_dict = speicher_dict["Server"]
		joy_dict = speicher_dict["Joystick"]
		
		try:
			self.socket_init(server_dict["Host"], int(server_dict["Port"]), loks)
			self.scrolled_window = ScrolledWindow(self.socket, loks, self) # ScrolledWindow und darin HBox für Regler erzeugen
			self.nothalt_button = Nothaltbutton(self.socket) # HBox für Notstop erzeugen
			self.konfiguration_button = KonfigurationButton(self, self.config_fenster)
			self.fullscreen_button = FullscreenButton(self)
			
			self.hbox_oben = Gtk.HBox()
			self.hbox_oben.pack_start(self.konfiguration_button, True, True, 0)
			self.hbox_oben.pack_start(self.fullscreen_button, False, False, 0)
			
			self.grundbox = Gtk.VBox() # Grundbox erzeugen
			self.grundbox.pack_start(self.hbox_oben, False, False, 0)
			self.grundbox.pack_start(self.scrolled_window, True, True, 0)
			self.grundbox.pack_start(self.nothalt_button, False, False, 0)
			self.add(self.grundbox)
			
			self.joystick_konsole = joystick_konsole.JoystickKonsole(loks, self.scrolled_window.hbox_mitte.regler, self.nothalt_button, joy_dict)
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
			self.config_fenster.show_all()
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

class KonfigurationButton(Gtk.ToggleButton):
	def __init__(self, fenster, config_fenster):
		super(KonfigurationButton, self).__init__("Konfiguration")
		self.set_size_request(-1, 30)
		self.connect("clicked", self.clicked, fenster, config_fenster)
	
	def clicked(self, button, fenster, config_fenster):
		if config_fenster.get_property("visible"):
			config_fenster.hide()
			if fenster.is_fullscreen:
				fenster.fullscreen()
		else:
			if fenster.is_fullscreen:
				fenster.unfullscreen()
			config_fenster.show_all()
		self.toggled()

class FullscreenButton(Gtk.ToggleButton):
	def __init__(self, fenster):
		super(FullscreenButton, self).__init__()
		icon = Gtk.Image()
		icon.set_from_stock(Gtk.STOCK_FULLSCREEN, Gtk.IconSize.BUTTON)
		label = Gtk.Label(label="Vollbild")
		hbox = Gtk.HBox(False, 5)
		hbox.pack_start(label, True, True, 0)
		hbox.pack_start(icon, True, True, 0)
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
		
class ScrolledWindow(Gtk.ScrolledWindow):
	def __init__(self, socket, loks, fenster):
		super(ScrolledWindow, self).__init__()
		self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.hbox_mitte = HBoxMitte(socket, loks, fenster, self)
		self.add_with_viewport(self.hbox_mitte)
		
class HBoxMitte(Gtk.HBox):
	def __init__(self, socket, loks, fenster, scrolled_window):
		super(HBoxMitte, self).__init__()
		self.regler = []
		self.socket = socket
		for i in range(len(loks)): # Alle Regler hinzufügen
			self.regler.append(Regler(socket, loks[i], scrolled_window))
			self.pack_start(self.regler[i], True, True, 0)
		self.connect("realize", self.realized, fenster)
				
	def realized(self, hbox, fenster):
		min_req, natural_req = self.get_preferred_size()
		#width, height = self.size_request()
		fenster.resize(natural_req.width + 100, natural_req.height + 100)
		
		max_funktionsbuttons = 0
		search_pending = True # Suche nach einem Funktionsbutton um Höhe zu ermitteln
		for regler in self.regler:
			regler.hbox = HBoxFunktionen(regler.lok, self.socket)
			regler.hbox.show_all()
			regler.pack_start(regler.hbox, False, False, 10)
			if regler.hbox.max_anzahl_buttons > max_funktionsbuttons: # finde spalte mit den meisten buttons (mit der bedingung geht einher, dass regler.hbox mindestens einen Funktionsbutton besitzt)
				max_funktionsbuttons = regler.hbox.max_anzahl_buttons
				if search_pending:
					button_req = regler.hbox.buttons[0].get_preferred_size()[1]
					search_pending = False
					
		for regler in self.regler:
			if len(regler.hbox.boxen) > 0:	
				for box in regler.hbox.boxen:
					box.set_size_request(-1, button_req.height * max_funktionsbuttons)
			else:
				regler.hbox.set_size_request(-1, button_req.height * max_funktionsbuttons)
			

class Regler(Gtk.VBox):
	def __init__(self, socket, lok, scrolled_window):
		super(Regler, self).__init__()
		self.lok = lok
		self.joystick = None
		self.lokbild = Lokbild(lok.bild)
		self.geschwindigkeitsregler = Geschwindigkeitsregler(lok, socket)
		self.lokschild = Lokschild(lok)
		self.richtungswender = Richtungswender(lok, socket, self.geschwindigkeitsregler)
		self.gamepad_bild = Gtk.Image()
		self.gamepad_bild.set_size_request(110, 50)
		self.scrolled_window = scrolled_window
		
		self.pack_start(self.lokbild, False, False, 0)
		self.pack_start(self.geschwindigkeitsregler, True, True, 0)
		self.pack_start(self.lokschild, False, False, 0)
		self.pack_start(self.gamepad_bild, False, False, 0)
		self.pack_start(self.richtungswender, False, False, 0)
		
	def set_focus(self): # Regler im ScrolledWindow sichtbar machen
		adjust = self.scrolled_window.get_hadjustment()
		adjust.clamp_page(self.allocation.x, self.allocation.x + self.allocation.width)
	
class Lokbild(Gtk.Image):
	def __init__(self, pfad):
		super(Lokbild, self).__init__()
		self.set_size_request(110, 85)
		if pfad == None:
			self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
		else:
			try:
				pixbuf= GdkPixbuf.Pixbuf.new_from_file(pfad)
				small_pixbuf = pixbuf.scale_simple(110 , 85, GdkPixbuf.InterpType.BILINEAR)
				self.set_from_pixbuf(small_pixbuf)
			except GError:
				self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
				locked_print(u"Dateipfad '" + pfad + u"' für Lokbild ist ungültig.")

class Geschwindigkeitsregler(Gtk.Scale):
	def __init__(self, lok, socket):
		self.fahrstufen = Gtk.Adjustment(0, 0, lok.fahrstufen, 1, 0, 0)
		super(Geschwindigkeitsregler, self).__init__()
		self.set_orientation(Gtk.Orientation.VERTICAL)
		self.set_adjustment(self.fahrstufen)
		self.connect("value-changed", self.geschw_aenderung, lok, socket)
		self.set_inverted(True)
		self.set_digits(1)
		self.set_value_pos(Gtk.PositionType.BOTTOM)

	def geschw_aenderung(self, scale, lok, socket):
		geschw_aktuell = self.get_value()
		lok.geschwindigkeit = geschw_aktuell
		locked_print("Lok", lok.name, u"fährt jetzt", lok.geschwindigkeit, ", das entspricht", int(lok.geschwindigkeit), "Fahrstufen.")
		if int(lok.geschwindigkeit) != lok.letzte_gesendete_geschwindigkeit:
			lok.an_server_senden(socket)

class Lokschild(Gtk.Label):
	def __init__(self, lok):
		self.text = lok.name
		super(Lokschild, self).__init__(self.text)
		self.set_ellipsize(Pango.EllipsizeMode.END)
	
	def set_bold(self, bold):
		if bold:
			self.set_markup("<b>" + self.text + "</b>")
		else:
			self.set_markup(self.text)

class Richtungswender(Gtk.Button):
	def __init__(self, lok, socket, scale):
		super(Richtungswender, self).__init__()
		self.set_size_request(-1, 30)
		self.pfeil_hoch = Gtk.Arrow.new(Gtk.ArrowType.UP, Gtk.ShadowType.NONE)
		self.pfeil_runter = Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.NONE)
		self.zeige_richtungspfeil(lok.richtung)
		self.connect("clicked", self.richtungswechsel, lok, socket, scale)

	def richtungswechsel(self, button, lok, socket, scale):
		lok.richtung = not lok.richtung
		locked_print("\nLok", lok.name, u"hat die Richtung gewechselt und fährt nun", lok.richtung)
		
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

class FunktionButton(Gtk.ToggleButton):
	def __init__(self, lok, funktionsname, wert, nr, socket):
		self.text = funktionsname
		super(FunktionButton, self).__init__(self.text)
		self.child_label = self.get_child()
		self.child_label.set_ellipsize(Pango.EllipsizeMode.END)
		self.wert = wert
		if self.wert:
			self.set_active(True)
		self.connect("clicked", self.funktion_umschalten, lok, nr, socket)
		

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
			
class HBoxFunktionen(Gtk.HBox):
	def __init__(self, lok, socket):
		super(HBoxFunktionen, self).__init__()
		self.boxen = []
		self.max_anzahl_buttons = 0
		self.buttons = [FunktionButton(lok, funktion["Name"], funktion["Wert"], funktion["Nr"], socket) for funktion in lok.funktionen] # erzeuge funktionsbuttons
		
		if len(lok.funktionen) > 0:			
			anzahl_boxen, rest_boxen = divmod(len(lok.funktionen), CONTROL_NUMBER_FUNCTION_BUTTONS) # ermittle, wie viele boxen erzeugt werden müssen
			if rest_boxen > 0:
				anzahl_boxen += 1
			buttons_pro_box, rest_buttons = divmod(len(lok.funktionen), anzahl_boxen) # ermittle, wie viele buttons in eine box kommen, wenn sie gleichmäßig verteilt werden sollen
			
			zu_packende_buttons = len(lok.funktionen)

			for box_nr in range(int(anzahl_boxen)):
				box = Gtk.VButtonBox()
				box.set_layout(Gtk.ButtonBoxStyle.START)
				
				if zu_packende_buttons > buttons_pro_box:
					pack_anzahl = buttons_pro_box
				else:
					pack_anzahl = zu_packende_buttons
				
				if rest_buttons > 0:
					pack_anzahl += 1
					rest_buttons -= 1
				
				for i in range(pack_anzahl):
					box.pack_start(self.buttons[len(lok.funktionen)-zu_packende_buttons + i], True, True, 0)					
				
				zu_packende_buttons -= pack_anzahl
				
				if pack_anzahl > self.max_anzahl_buttons:
					self.max_anzahl_buttons = pack_anzahl
					
				self.boxen.append(box)
				self.pack_start(box, True, True, 0)

class Nothaltbutton(Gtk.ToggleButton):
	def __init__(self, socket):
		super(Nothaltbutton, self).__init__()
		self.set_label("Nothalt")
		self.set_size_request(-1 , 60)
		self.socket = socket
		self.strom_an = False
		
		rot = Gdk.RGBA(*CONTROL_EMERGENCY_COLOR_RED)
		dunkelgrau = Gdk.RGBA(*CONTROL_EMERGENCY_COLOR_DARK_GREY)
		
		#self.override_background_color(Gtk.StateFlags.ACTIVE, rot) # Funktioniert nicht
		#child_label = self.get_child()
		#child_label.override_color(Gtk.StateFlags.ACTIVE, dunkelgrau)
		
		self.connect("clicked", self.set_strom)
		self.set_strom()
	
	def set_strom(self, *args):
		self.strom_an = not self.strom_an
		if self.strom_an:
			self.socket.send("SET 1 POWER ON\n")
			locked_print("\nStrom angeschaltet")
		else:
			self.socket.send("SET 1 POWER OFF\n")
			locked_print("\nNotstop eingeleitet")
		self.toggled()
