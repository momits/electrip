#!/usr/bin/env python
# -*- coding: UTF 8 -*-
# this is ELECTRIP VERSION 1.6.0

# Import von Modulen

import cPickle as pickle
import gobject
import gtk
from Lok import Lok
import SaveAndLoad
import ELECTRIP_Control
from LockedPrint import locked_print
import pango
from sys import argv

class Fenster(gtk.Window):
	def __init__(self, titel):
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		self.set_title(titel)
		self.connect("delete-event", self.delete_event)
		self.control_window_is_alive = False # Zu Beginn gibt es kein aktives Control-Window
		if len(argv) > 2 and (argv[1] == "-f" or argv[1] == "--file"):
				verzeichnis = argv[2]
		else:
			verzeichnis = None
		self.grundbox = Grundbox(self, verzeichnis)
		self.add(self.grundbox)
		if verzeichnis == None:
			self.show_all()
		else:
			success = self.grundbox.buttonbox_oben.ladebutton.laden(verzeichnis, self)
			if success:
				self.grundbox.buttonbox_oben.electrip_ladebutton.in_electrip_laden(None, self)
			else:
				self.show_all()
		
	def delete_event(self, window, event):
		if self.grundbox.has_unsaved_changes:
			dialog = gtk.MessageDialog(self, 0, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, "Die Datei besitzt, ungespeicherte Änderungen.\n Wollen Sie diese speichern?")
			response = dialog.run()
			dialog.destroy()
			if response == gtk.RESPONSE_YES and self.grundbox.verzeichnis == None:
				self.grundbox.buttonbox_oben.speichern_unter_button.speichern(None, self)
			elif response == gtk.RESPONSE_YES:
				speicherdict = self.grundbox.get_speicherdict()
				pickle.dump(speicherdict, open(self.grundbox.verzeichnis, 'wb'))
		if self.control_window_is_alive:
			self.steuerungsfenster.delete_event()
		gtk.main_quit()
		locked_print("ELECTRIP wurde beendet.")
	
	def error(self, warnung):
		fehlermeldung = gtk.MessageDialog(self, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, warnung)
		fehlermeldung.run()
		fehlermeldung.destroy()

class Grundbox(gtk.VBox):
	def __init__(self, fenster, verzeichnis):
		gtk.VBox.__init__(self, False, 0)
		self.has_unsaved_changes = False # Zu Beginn keine ungespeicherten Änderungen
		self.verzeichnis = verzeichnis # Zu Beginn ist keine Datei geladen
		
		self.hbox_mitte = HBoxMitte(self.status_changed)
		self.hbox_sonstiges = HBoxSonstiges(self.status_changed)
		self.buttonbox_oben = Buttonbox_oben(self.hbox_mitte.lok_frame.scrolled_window.lokliste, self.hbox_mitte.funktionen_frame.function_mapping_box, self.hbox_sonstiges, fenster)

		self.pack_start(self.buttonbox_oben, False)
		self.pack_start(self.hbox_mitte)
		self.pack_start(self.hbox_sonstiges, False)
		
		# Widgets mit leerem Inhalt füllen
		self.hbox_sonstiges.server_frame.laden({"Host": "", "Port": ""}) # Laden mit leerem server_dict
		self.hbox_sonstiges.joy_frame.laden({"Notstop": "", "Richtungswender": "", "Achse": "", "Fokus": ""}) # Laden mit leerem joydict
		
	def status_changed(self, widget, unsaved_changes):
		if unsaved_changes and not self.has_unsaved_changes: # wenn status gewechselt hat
			self.has_unsaved_changes = True
			if self.verzeichnis != None:
				self.buttonbox_oben.speicherbutton.set_sensitive(True)
			print "Widget", widget, "meldet ungespeicherte Änderungen."
		elif not unsaved_changes and self.has_unsaved_changes:
			self.has_unsaved_changes = False
			self.buttonbox_oben.speicherbutton.set_sensitive(False)
	
	def get_speicherdict(self):
		# Dictionary mit allen Konfigurationsdaten der Benutzeroberfläche erzeugen
		
		# 1. Erstellt eine Liste der Form <ID> <Name> <Bildpfad> <Adresse> <Protokoll> <Fahrstufen> <Fahrtrichtung (True = vorwärts)> <Beschleunigungszeit in s> <Funktionsliste {name, sende_nr, wert, Joybutton} und erzeugt daraus Lokobjekte
		liste = self.hbox_mitte.lok_frame.scrolled_window.lokliste.liste
		funktionslisten = self.hbox_mitte.funktionen_frame.function_mapping_box.funktionslisten
		loks = []
		row_nr = 0
		standard_funktionsdict = ["Nr","Name","SendeNr","Wert","Button", "Taster"]
		for row in liste:
			lok = []
			funktionen = []
			nummer = 0
			for eigenschaft in row:
				# dafür sorgen dass die Fahrtrichtung in boolean konvertiert wird:
				if eigenschaft == 'Vorwärts':
					eigenschaft = True
				elif eigenschaft == 'Rückwärts':
					eigenschaft = False
				lok.append(eigenschaft)
				nummer += 1

			for row in funktionslisten[row_nr]:
				funktion = {}
				nummer = 0
				for eigenschaft in row:
					eigenschaft_name = standard_funktionsdict[nummer]
					if eigenschaft_name == "Taster": # dafür sorgen dass Taster in Boolean konvertiert wird
						if eigenschaft == 'Taster':
							eigenschaft = True
						elif eigenschaft == 'Umschalter':
							eigenschaft = False
					elif eigenschaft_name == "Wert": # dafür sorgen dass der Wert (An oder Aus) in boolean konvertiert wird
						if eigenschaft == 'An':
							eigenschaft = True
						elif eigenschaft == 'Aus':
							eigenschaft = False
					funktion[eigenschaft_name] = eigenschaft
					nummer += 1
				funktionen.append(funktion)
			row_nr += 1
			lok.append(funktionen)
			lok_instanz = Lok(*lok) # Liste in Parameter für Lokobjekt verwandeln
			loks.append(lok_instanz)
			
		# 2. Serverdict der Form {"Host": host, "Port": port} erzeugen
		server = {}
		server_frame = self.hbox_sonstiges.server_frame
		i = 0
		for parameter in server_frame.parameter:
			wert = server_frame.eingabefelder[i].get_text()
			server[parameter] = wert
			i += 1
		try:
			server["Port"] = int(server["Port"])
		except ValueError:
			print "Server-Parameter Port ist nicht gültig."
			server["Port"] = "" # Setze Server-Port auf leer, weil Angabe unkorrekt
			
		# 3. Joystickdict der Form {"Notstop": notstopbutton, "Richtungswender": wendebutton, "Achse": joyachse} erzeugen
		joystick = {}
		joy_frame = self.hbox_sonstiges.joy_frame
		i = 0
		for parameter in joy_frame.speicher_parameter:
			try:
				wert = joy_frame.eingabefelder[i].get_text()
				wert = int(wert)
				joystick[parameter] = wert
			except ValueError:
				print "Joystick-Parameter", parameter, "ist nicht gültig."
				joystick[parameter] = "" # Setze Parameter auf leer, weil Angabe unkorrekt
			i += 1
		
		# Finales Speicherdict erzeugen
		speicher_dict = {"Loks": loks, "Server": server, "Joystick": joystick}
		return speicher_dict

class StockBildButton(gtk.Button):
	def __init__(self, label, stock):
		gtk.Button.__init__(self)
		icon = gtk.Image()
		icon.set_from_stock(stock, gtk.ICON_SIZE_BUTTON)
		label = gtk.Label(label)
		hbox = gtk.HBox(False, 5)
		hbox.pack_start(label)
		hbox.pack_start(icon)
		self.add(hbox)

class Legendebutton(StockBildButton):
	def __init__(self):
		StockBildButton.__init__(self, "Legende...", gtk.STOCK_HELP)
		self.legende = Legendefenster()
		self.connect("clicked", self.legende_zeigen)
		
	def legende_zeigen(self, *args):
		self.legende.show_all()

class Legendefenster(gtk.Window):
	def __init__(self):
		gtk.Window.__init__(self)
		self.set_title("Legende / Erläuterungen")
		self.connect("delete-event", self.delete_event)
		self.tabelle = Legendetabelle()
		self.add(self.tabelle)
		
	def delete_event(self, *args):
		self.hide()
		return True

class Legendetabelle(gtk.Table):
	def __init__(self):
		gtk.Table.__init__(self, 11, 2)
		self.begriffe = ["ID", "Lok", "Protokoll", "Fahrstufen", "Beschleunigungszeit", "Fahrtrichtung", "Bild", "Funktionsname", "SendeNr", "Wert", "JoyButton", "Schaltart"]
		i = 0
		for begriff in self.begriffe:
			label = Beschriftung(begriff)
			self.attach(label, 0, 1, i, (i+1))
			i = i + 1
		self.definitionen = [
		"Die Nummer, die über die Anzeigereihenfolge der Loks im Fahrprogramm entscheidet:\nKleine Zahl links, große Zahl rechts",
		"Der Name der Lok",
		"Das Digitalprotokoll, dass vom Lokdecoder verwendet wird:\n	-> M 1: Märklin Motorola 1. Version\n	-> M 2: Märklin Motorola 2. Version\n	-> N1: DCC kurzes Adressformat\n	-> N2: DCC langes Adressformat",
		"Die Anzahl Fahrstufen, die der Lokdecoder besitzt",
		"Die Zeit, die benötigt wird, um die Fahrstufe der Lok bei voller Auslenkung\ndes Joysticks von 0 auf den höchstmöglichen Wert zu bringen.",
		"Die voreingestellte Fahrtrichtung der Lokomotive",
		"Der Pfad an dem das passende Lokbild abgelegt ist",
		"Der Name der Funktion ('Licht', 'Hupe' ...)",
		"Die Nummer der Funktion im Lokdecoder",
		"Der voreingestellte Zustand der Funktion: An oder Aus",
		"Der Button am JoyStick, dem die Lokfunktion zugewiesen ist",
		"Die Art, mit der eine Funktion durch einen Joystick-Button geschaltet wird: Taster oder Umschalter"
		]
		i = 0
		for definition in self.definitionen:
			frame = gtk.Frame(definition)
			frame.set_label_align(0.0, 0.0)
			self.attach(frame, 1, 2, i, (i+1))
			i = i + 1
		self.set_col_spacing(0, 22)
		self.set_row_spacings(5)

class Ladebutton(StockBildButton):
	def __init__(self, lok_treeview, funktions_treeview, hbox_sonstiges, fenster):
		StockBildButton.__init__(self, "Laden", gtk.STOCK_OPEN)
		self.lok_treeview = lok_treeview
		self.funktions_treeview = funktions_treeview
		self.hbox_sonstiges = hbox_sonstiges
		
		self.connect("clicked", self.lade_dialog, fenster)
		
	def lade_dialog(self, button, fenster):
		file_chooser_dialog = SaveAndLoad.DateiLadenDialog(fenster)
		try:
			letzter_pfad = pickle.load(open("electrip.conf"))
			file_chooser_dialog.set_filename(letzter_pfad)
		except IOError:
			print "Bisher keine Standardeinstellungen gespeichert."
		response = file_chooser_dialog.run()
		if response == gtk.RESPONSE_OK:
			verzeichnis = file_chooser_dialog.get_filename()
			self.laden(verzeichnis, fenster)
			fenster.show_all()
		elif response == gtk.RESPONSE_CANCEL:
			print 'Laden abgebrochen.'
		file_chooser_dialog.destroy()
		print
		
	def laden(self, verzeichnis, fenster):
		try:
			speicher_dict = pickle.load(open(verzeichnis))
			loks = speicher_dict["Loks"]
			server = speicher_dict["Server"]
			joystick = speicher_dict["Joystick"]
			self.lok_treeview.laden(loks) # loks
			self.funktions_treeview.laden(loks) # loks
			self.hbox_sonstiges.joy_frame.laden(joystick) # joystick
			self.hbox_sonstiges.server_frame.laden(server) # server
			pickle.dump(verzeichnis, open("electrip.conf", 'wb'))
			fenster.grundbox.verzeichnis = verzeichnis
			fenster.grundbox.status_changed(None, False)
			print "Einstellungen wurden aus " + verzeichnis + " geladen."
			fenster.set_title("ELECTRIP - Konfiguration - " + verzeichnis)
			return True
		except pickle.UnpicklingError:
			fenster.error("Laden gescheitert.\nEs handelt sich um keine gültige ELECTRIP-Datei.")
			return False
		except IOError:
			fenster.error("Der Dateipfad ist ungültig! Konnte Konfiguration nicht laden.")
			return False

class SpeichernUnterButton(StockBildButton):
	def __init__(self, fenster):
		StockBildButton.__init__(self, "Speichern unter", gtk.STOCK_SAVE_AS)
		self.connect("clicked", self.speichern, fenster)
		
	def speichern(self, button, fenster):
		file_chooser_dialog = SaveAndLoad.DateiSpeichernDialog(fenster)
		if fenster.grundbox.verzeichnis == None:
			try:
				letzter_pfad = pickle.load(open("electrip.conf"))
				file_chooser_dialog.set_filename(letzter_pfad)
			except:
				print "Bisher keine Standardeinstellungen gespeichert."
		else:
			file_chooser_dialog.set_filename(fenster.grundbox.verzeichnis)
		response = file_chooser_dialog.run()
		if response == gtk.RESPONSE_OK:
			verzeichnis = file_chooser_dialog.get_filename()
			speicherdict = fenster.grundbox.get_speicherdict()
			if verzeichnis != "" and verzeichnis[len(verzeichnis)-4:len(verzeichnis)] != ".elc": # Wenn Dateiendung fehlt und ein Dateiname angegeben wurde, Endung anhängen
				verzeichnis += ".elc"
			pickle.dump(speicherdict, open(verzeichnis, 'wb'))
			pickle.dump(verzeichnis, open("electrip.conf", 'wb'))
			print "Einstellungen wurden gespeichert in " + verzeichnis
			fenster.set_title("ELECTRIP - Konfiguration - " + verzeichnis)
			fenster.grundbox.verzeichnis = verzeichnis
		elif response == gtk.RESPONSE_CANCEL:
			print 'Speichern abgebrochen.'
		file_chooser_dialog.destroy()

class SpeicherButton(StockBildButton):
	def __init__(self, fenster):
		StockBildButton.__init__(self, "Speichern", gtk.STOCK_SAVE)
		self.connect("clicked", self.speichern, fenster)
		self.set_sensitive(False)
		
	def speichern(self, button, fenster):
		speicherdict = fenster.grundbox.get_speicherdict()
		pickle.dump(speicherdict, open(fenster.grundbox.verzeichnis, 'wb'))
		fenster.grundbox.status_changed(None, False)

class ElectripLadebutton(StockBildButton):
	def __init__(self, fenster):
		StockBildButton.__init__(self, "In ELECTRIP-Steuerung laden", gtk.STOCK_EXECUTE)
		self.connect("clicked", self.in_electrip_laden, fenster)
		fenster.steuerungsfenster = None
	
	def in_electrip_laden(self, button, fenster):
		fenster.hide()
		if fenster.steuerungsfenster != None:
			fenster.steuerungsfenster.delete_event(show_config_fenster=False) # Alte Steuerung beenden und danach nicht das Konfigurationsfenster einblenden, sondern ein neues Steuerungsfenster starten
		fenster.steuerungsfenster = ELECTRIP = ELECTRIP_Control.Fenster("ELECTRIP 1.6.0", fenster)

class Buttonbox_oben(gtk.HBox):
	def __init__(self, lokliste, function_mapping_box, hbox_sonstiges, fenster):
		gtk.HBox.__init__(self, False)
		self.legendebutton = Legendebutton()
		self.ladebutton = Ladebutton(lokliste, function_mapping_box, hbox_sonstiges, fenster)
		self.speichern_unter_button = SpeichernUnterButton(fenster)
		self.speicherbutton = SpeicherButton(fenster)
		self.electrip_ladebutton = ElectripLadebutton(fenster)
		
		self.pack_start(self.legendebutton, False)
		self.pack_start(self.ladebutton, False)
		self.pack_start(self.speichern_unter_button, False)
		self.pack_start(self.speicherbutton, False)
		self.pack_start(self.electrip_ladebutton, False)

class NeueLokButton(gtk.Button):
	def __init__(self, loktreeview, funktionsbox, save_status_method):
		gtk.Button.__init__(self, "Neue Lok")
		self.connect("clicked", self.neue_lok, loktreeview, funktionsbox)
		self.save_status_method = save_status_method
		
	def neue_lok(self, button, loktreeview, funktionsbox):
		funktionsbox.funktionslisten.append(gtk.ListStore(*funktionsbox.column_types))
		nr = len(loktreeview.liste)
		werte = loktreeview.column_standard_values
		werte[0] = nr
		loktreeview.liste.append(werte)
		self.save_status_method(button, True)

class LokLoeschenButton(gtk.Button):
	def __init__(self, loktreeview, funktionsbox, save_status_method):
		gtk.Button.__init__(self, "Lok löschen")
		self.connect("clicked", self.lok_loeschen, loktreeview, funktionsbox)
		self.save_status_method = save_status_method
		
	def lok_loeschen(self, button, loktreeview, funktionsbox):
		try:
			path = loktreeview.get_cursor()[0]
			zeile = loktreeview.liste.get_iter(loktreeview.sort_model.convert_path_to_child_path(path)) # Zu löschende Zeile im Liststore finden: != ausgewählte Zeile im SortModel
			funktionsbox.funktionslisten.remove(funktionsbox.get_model()) # Aktuelle Funktionsliste löschen
			loktreeview.liste.remove(zeile) # Zeile im Liststore löschen
			loktreeview.nummerieren()
			self.save_status_method(button, True)
		except TypeError:
			locked_print("Keine Zeile ausgewählt.")

class FunktionLoeschenButton(gtk.Button):
	def __init__(self, funktionsbox, save_status_method):
		gtk.Button.__init__(self, "Funktion löschen")
		self.connect("clicked", self.funktion_loeschen, funktionsbox)
		self.save_status_method = save_status_method
		
	def funktion_loeschen(self, button, funktionsbox):
		liste = funktionsbox.get_model() # Aktuelle Funktionsliste finden
		path = funktionsbox.get_cursor()[0]
		if path != None:
			zeile = liste.get_iter(path) # Zu löschende Zeile im Liststore finden
			liste.remove(zeile) # Zeile im Liststore löschen
			funktionsbox.nummerieren()
		self.save_status_method(button, True)

class NeueFunktionButton(gtk.Button):
	def __init__(self, funktionsbox, save_status_method):
		gtk.Button.__init__(self, "Neue Funktion")
		self.connect("clicked", self.neue_funktion, funktionsbox)
		self.save_status_method = save_status_method
		
	def neue_funktion(self, button, funktionsbox):
		try:
			funktionsliste = funktionsbox.get_model()
			nr = len(funktionsliste)
			werte = funktionsbox.column_standard_values
			werte[0] = nr
			funktionsliste.append(werte)
			self.save_status_method(button, True)
		except TypeError:
			print "Keine Lok ausgewählt."

class ButtonboxLokAktionen(gtk.HButtonBox):
	def __init__(self, loktreeview, funktionsbox, save_status_method):
		gtk.HButtonBox.__init__(self)
		self.set_layout(gtk.BUTTONBOX_START)
		self.neue_lok_button = NeueLokButton(loktreeview, funktionsbox, save_status_method)
		self.lok_loeschen_button = LokLoeschenButton(loktreeview, funktionsbox, save_status_method)
		
		self.add(self.neue_lok_button)
		self.add(self.lok_loeschen_button)

class ButtonboxFunktionAktionen(gtk.HButtonBox):
	def __init__(self, funktionsbox, save_status_method):
		gtk.HButtonBox.__init__(self)
		self.set_layout(gtk.BUTTONBOX_START)
		self.neue_funktion_button = NeueFunktionButton(funktionsbox, save_status_method)
		self.funktion_loeschen_button = FunktionLoeschenButton(funktionsbox, save_status_method)
		
		self.add(self.neue_funktion_button)
		self.add(self.funktion_loeschen_button)

class Beschriftung(gtk.Label):
	def __init__(self, text):
		gtk.Label.__init__(self)
		self.set_markup("<b>" + text + "</b>")

class VBoxMitte(gtk.VBox): # VBoxen für Lokframe und FunktionenFrame
	def __init__(self, widget1, widget2):
		gtk.VBox.__init__(self)
		self.pack_start(widget1)
		self.pack_start(widget2, False, False)
		self.set_border_width(10)

class HBoxMitte(gtk.HBox):
	def __init__(self, save_status_method):
		gtk.HBox.__init__(self)

		self.funktionen_frame = FunktionenFrame(save_status_method)
		self.lok_frame = LokFrame(self.funktionen_frame.function_mapping_box, save_status_method)

		self.pack_start(self.lok_frame)
		self.pack_start(self.funktionen_frame)

class HBoxSonstiges(gtk.HBox):
	def __init__(self, save_status_method):
		gtk.HBox.__init__(self)
		self.server_frame = ServerFrame(save_status_method)
		self.joy_frame = JoystickFrame(save_status_method)
		self.pack_start(self.server_frame, False, False)
		self.pack_start(self.joy_frame, False, False)

class FunktionenFrame(gtk.Frame):
	def __init__(self, save_status_method):
		gtk.Frame.__init__(self)
		self.set_border_width(10) # Schönheitsabstand
		self.beschriftung = Beschriftung("Lokfunktionen")
		self.set_label_widget(self.beschriftung)
		self.set_shadow_type(gtk.SHADOW_OUT)
		
		self.function_mapping_box = FunctionMappingBox(save_status_method)
		self.buttonbox_funktionen = ButtonboxFunktionAktionen(self.function_mapping_box, save_status_method)
		
		self.vbox = VBoxMitte(self.function_mapping_box, self.buttonbox_funktionen)
		self.add(self.vbox)

class LokFrame(gtk.Frame):
	def __init__(self, function_mapping_box, save_status_method):
		gtk.Frame.__init__(self)
		self.set_border_width(10) # Schönheitsabstand
		self.beschriftung = Beschriftung("Lok")
		self.set_label_widget(self.beschriftung)
		self.set_shadow_type(gtk.SHADOW_OUT)
		
		self.scrolled_window = ScrolledWindow(function_mapping_box, save_status_method)
		self.buttonbox_lok = ButtonboxLokAktionen(self.scrolled_window.lokliste, function_mapping_box, save_status_method)
		
		self.vbox = VBoxMitte(self.scrolled_window, self.buttonbox_lok)
		self.add(self.vbox)

class ServerFrame(gtk.Frame):
	def __init__(self, save_status_method):
		gtk.Frame.__init__(self)
		self.set_border_width(10) # Schönheitsabstand
		self.beschriftung = Beschriftung("Server")
		self.set_label_widget(self.beschriftung)
		self.set_shadow_type(gtk.SHADOW_OUT)
		self.parameter = ["Host", "Port"]
		self.eingabefelder = []
		self.save_status_method = save_status_method

	def laden(self, server_dict):
		del self.eingabefelder[:]
		try:
			self.remove(self.table)
		except:
			pass
		self.table = gtk.Table(2, 3)
		self.table.set_col_spacings(10)
		self.table.set_row_spacings(5)
		self.table.set_border_width(6) # Schönheitsabstand
		
		i = 0
		for parameter in self.parameter:
			eingabefeld = gtk.Entry()
			eingabefeld.set_text(str(server_dict[parameter]))
			eingabefeld.connect("changed", self.save_status_method, True)
			self.eingabefelder.append(eingabefeld)
			label = gtk.Label(parameter)
			self.table.attach(label, 0, 1, i, (i+1))
			self.table.attach(self.eingabefelder[i], 1, 2, i, (i+1))
			i += 1
		self.add(self.table)

class JoystickFrame(gtk.Frame):
	def __init__(self, save_status_method):
		gtk.Frame.__init__(self)
		self.set_border_width(10) # Schönheitsabstand
		self.beschriftung = Beschriftung("Joystick")
		self.set_label_widget(self.beschriftung)
		self.set_shadow_type(gtk.SHADOW_OUT)
		self.speicher_parameter = ["Notstop", "Richtungswender", "Achse", "Fokus"]
		self.parameter = ["Notstop (JoyButton)", "Richtungswender (JoyButton)", "Beschleunigung (JoyAchse)", "Fokus (JoyButton)"] # Diese liste dient der besseren Verständlichkeit, die bei den speicher-parametern nicht so wichtig ist (und außerdem zu lang zum schreiben)
		self.eingabefelder = []
		self.save_status_method = save_status_method
		
	def laden(self, joydict):
		del self.eingabefelder[:]
		try: # Wenn Tabelle vorhanden, dann löschen
			self.remove(self.table)
		except:
			pass
		self.table = gtk.Table(2, 3)
		self.table.set_col_spacings(10)
		self.table.set_row_spacings(5)
		self.table.set_border_width(6) # Schönheitsabstand
		
		i = 0
		for parameter in self.speicher_parameter:
			eingabefeld = gtk.Entry()
			eingabefeld.set_text(str(joydict[parameter]))
			eingabefeld.connect("changed", self.save_status_method, True)
			self.eingabefelder.append(eingabefeld)
			label = gtk.Label(self.parameter[i])
			self.table.attach(label, i, (i+1), 0, 1)
			self.table.attach(self.eingabefelder[i], i, (i+1), 1, 2)
			i += 1
		self.add(self.table)

class FunctionMappingBox(gtk.TreeView):
	def __init__(self, save_status_method):
		self.funktionslisten = []
		self.save_status_method = save_status_method
		self.column_types = [gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_STRING]
		self.column_standard_values = [0, None, 0, "An", 0, "Umschalter"]
			
		# CellRenderer für Textfelder erzeugen
		self.textrenderer = gtk.CellRendererText()	
		self.textrenderer.set_property("editable", True)
		self.textrenderer.connect("editing_started", self.neue_editable)
		# CellRenderer für nicht editierbare Textfelder erzeugen
		self.textrenderer_not_editable = gtk.CellRendererText()
		
		# CellRenderer für Combobox erzeugen
		self.comborenderer = []
		for i in range(2): # Liste mit CellRendererCombos auffüllen
			self.comborenderer.append(gtk.CellRendererCombo())
			self.comborenderer[i].set_property("editable", True)
			self.comborenderer[i].set_property("has-entry", False)
			self.comborenderer[i].set_property("text-column", 0)
			self.comborenderer[i].connect("edited", self.neuer_wert)
		
		# Comborenderer 0 aus ListStore für Wert füllen
		self.combostore_wert = gtk.ListStore(gobject.TYPE_STRING)
		self.combostore_wert.append(["An"])
		self.combostore_wert.append(["Aus"])
		self.comborenderer[0].set_property("model", self.combostore_wert)
		
		# Comborenderer 1 aus ListStore für Taster füllen
		self.combostore_taster = gtk.ListStore(gobject.TYPE_STRING)
		self.combostore_taster.append(["Taster"])
		self.combostore_taster.append(["Umschalter"])
		self.comborenderer[1].set_property("model", self.combostore_taster)		

		gtk.TreeView.__init__(self)
		
		self.append_column(gtk.TreeViewColumn("Nr", self.textrenderer_not_editable, text = 0))
		self.append_column(gtk.TreeViewColumn("Funktionsname", self.textrenderer, text = 1))
		self.append_column(gtk.TreeViewColumn("SendeNr", self.textrenderer, text = 2))
		self.append_column(gtk.TreeViewColumn("Wert", self.comborenderer[0], text = 3))
		self.append_column(gtk.TreeViewColumn("JoyButtton", self.textrenderer, text = 4))
		self.append_column(gtk.TreeViewColumn("Schaltart", self.comborenderer[1], text = 5))
		
		nr = 0
		for column in self.get_columns(): # Versehe jede Spalte mit einer Nummer, zur leichten Identifizierung
			column.set_data("colnr", nr)
			nr += 1
	
	def laden(self, loks):
		del self.funktionslisten[:]
		i = 0
		self.loks = loks
		for lok in self.loks:
			self.funktionslisten.append(gtk.ListStore(*self.column_types))
			for funktion in lok.funktionen:
					if funktion["Wert"]:
						wert = "An"
					else:
						wert = "Aus"
					if funktion["Taster"]:
						schaltart = "Taster"
					else:
						schaltart = "Umschalter"
					self.funktionslisten[i].append([funktion["Nr"], funktion["Name"], funktion["SendeNr"], wert, funktion["Button"], schaltart])
			i = i + 1	
		
	def neue_editable(self, textrenderer, editable, path):
		editable.connect("editing-done", self.neuer_wert, path)
		
	def nummerieren(self):
		liste = self.get_model()
		id = 0
		for row in liste:
			row[0] = id
			id += 1
	
	def neuer_wert(self, editable, path, text = None):
		liste = self.get_model()
		spalte = self.get_cursor()[1].get_data("colnr")
		
		if text == None:
			try:
				neuer_text = editable.get_text()
			except:
				neuer_text = editable.get_active_text()
		else:
			neuer_text = text
		
		if self.column_types[spalte] == gobject.TYPE_INT:
			try:
				liste[path][spalte] = int(neuer_text)
			except ValueError:
				print "Falsche Eingabe, Sie haben keinen Wert eingegeben, der in den Typ Integer umgewandelt werden kann."
		else:
			liste[path][spalte] = neuer_text
		self.save_status_method("Function Mapping Box", True)

class ScrolledWindow(gtk.ScrolledWindow):
	def __init__(self, function_mapping_box, save_status_method):
		gtk.ScrolledWindow.__init__(self)
		self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		self.lokliste = Lokliste(function_mapping_box, save_status_method)
		width, height = self.lokliste.size_request()
		self.set_size_request(width, height+40)
		self.add(self.lokliste)

class Lokliste(gtk.TreeView):
	def __init__(self, funktionenbox, save_status_method):
		self.column_types = [gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_FLOAT, gobject.TYPE_STRING, gobject.TYPE_STRING]
		self.column_standard_values = [0, None, 0 , "M 1", 14, 3, "Vorwärts", None]
		self.liste = gtk.ListStore(*self.column_types)
		self.funktionen_box = funktionenbox
		self.save_status_method = save_status_method
		
		# CellRenderer für Textfelder erzeugen
		self.textrenderer = gtk.CellRendererText()
		self.textrenderer.set_property("editable", True)
		self.textrenderer.set_property("ellipsize", pango.ELLIPSIZE_END)
		self.textrenderer.connect("editing_started", self.neue_editable)
		self.textrenderer_not_editable = gtk.CellRendererText()
		
		# CellRenderer-Liste für ComboBoxen erzeugen
		self.comborenderer = []
		for i in range(3): # Liste mit CellRendererCombos auffüllen
			self.comborenderer.append(gtk.CellRendererCombo())
			self.comborenderer[i].set_property("editable", True)
			self.comborenderer[i].set_property("text-column", 0)
			self.comborenderer[i].set_property("has-entry", False)
			self.comborenderer[i].connect("edited", self.neuer_wert)
		
		# ComboRenderer aus kleinen ListStores füllen
		# Combostore_Protokoll
		self.combostore_protokoll = gtk.ListStore(gobject.TYPE_STRING)
		self.combostore_protokoll.append(["M 1"])
		self.combostore_protokoll.append(["M 2"])
		self.combostore_protokoll.append(["N 1"])
		self.combostore_protokoll.append(["N 2"])
		self.comborenderer[0].set_property("model", self.combostore_protokoll)
		# Combostore_Fahrstufen
		self.combostore_fahrstufen = gtk.ListStore(gobject.TYPE_STRING) # Für CellRendererCombo muss Type String sein, sonst segfault!
		self.combostore_fahrstufen.append([14])
		self.combostore_fahrstufen.append([27])
		self.combostore_fahrstufen.append([28])
		self.combostore_fahrstufen.append([128])
		self.comborenderer[1].set_property("model", self.combostore_fahrstufen)
		# Combostore_Fahrtrichtung
		self.combostore_fahrtrichtung = gtk.ListStore(gobject.TYPE_STRING)
		self.combostore_fahrtrichtung.append(["Vorwärts"])
		self.combostore_fahrtrichtung.append(["Rückwärts"])
		self.comborenderer[2].set_property("model", self.combostore_fahrtrichtung)
		
		# SortModel erstellen: Verbindung zwischen angezeigter und gespeicherter Datenreihenfolge
		self.sort_model = gtk.TreeModelSort(self.liste)
		self.sort_model.set_sort_column_id(0, gtk.SORT_ASCENDING)
		gtk.TreeView.__init__(self, self.sort_model)
		self.connect("cursor-changed", self.lokauswahl)
		
		# Spalten hinzufügen
		self.append_column(gtk.TreeViewColumn("ID", self.textrenderer_not_editable, text = 0))
		self.append_column(gtk.TreeViewColumn("Lok", self.textrenderer, text = 1))
		self.append_column(gtk.TreeViewColumn("Adresse", self.textrenderer, text = 2))
		self.append_column(gtk.TreeViewColumn("Protokoll", self.comborenderer[0], text = 3))
		self.append_column(gtk.TreeViewColumn("Fahrstufen", self.comborenderer[1], text = 4))
		self.append_column(gtk.TreeViewColumn("Beschleunigungszeit", self.textrenderer, text = 5))
		self.append_column(gtk.TreeViewColumn("Fahrtrichtung", self.comborenderer[2], text = 6))
		self.append_column(gtk.TreeViewColumn("Bild", self.textrenderer, text = 7))
		
		i = 0
		for column in self.get_columns():
			column.set_sort_column_id(i)
			column.set_resizable(True) # Spalten vergrößerbar / verkleinerbar machen
			column.set_data("colnr", i) # Versehe jede Spalte mit einer Nummer, zur leichten Identifizierung
			i = i + 1
		
	def laden(self, loks):
		self.liste.clear()
		self.loks = loks
		for lok in self.loks:
			if lok.richtung:
				fahrtrichtung = "Vorwärts"
			else:
				fahrtrichtung = "Rückwärts"
			self.liste.append([lok.id, lok.name, lok.adresse, lok.protokoll, lok.fahrstufen, lok.beschleunigungszeit, fahrtrichtung, lok.bild])
		
	def neue_editable(self, renderer, editable, path):
		editable.connect("editing-done", self.neuer_wert, path)
	
	def nummerieren(self):
		id = 0
		for row in self.liste:
			row[0] = id
			id += 1

	def neuer_wert(self, editable, path, text = None):
		spalte = self.get_cursor()[1].get_data("colnr") # Rufe zugewiesene Eigenschaft "colnr" auf (siehe oben -> 'set_data')
		zeile = self.sort_model.convert_path_to_child_path(path) # Finde Zeile im Liststore über sort_model
		if text == None:
			try:
				neuer_text = editable.get_text()
			except:
				neuer_text = editable.get_active_text()
		else:
			neuer_text = text
		
		if self.column_types[spalte] == gobject.TYPE_INT:
			try:
				self.liste[path][spalte] = int(neuer_text)
			except ValueError:
				print "Falsche Eingabe, Sie haben keinen Wert eingegeben, der in den Typ Integer umgewandelt werden kann."
		elif self.column_types[spalte] == gobject.TYPE_FLOAT:
			try:
				self.liste[zeile][spalte] = float(neuer_text.replace(",",".")) # Kommas zur Umwandlung String-->Float durch Punkte ersetzen
			except ValueError:
				print "Falsche Eingabe: Sie haben keinen Wert eingegeben, der in den Typ Float umgewandelt werden kann."
		else:
			self.liste[path][spalte] = neuer_text
		self.save_status_method("Lokliste", True)

	def lokauswahl(self, treeview):
		cursor_path = self.get_cursor()[0] # Pfad zur angezeigten Zeile
		zeile = cursor_path[0]
		datenzeile = self.sort_model.convert_path_to_child_path(cursor_path)[0] # Zeile im Liststore durch Konvertierung des angezeigten Pfades in einen Liststorepfad ermitteln
		self.funktionen_box.set_model(self.funktionen_box.funktionslisten[datenzeile]) # Funktionenliste

if __name__ == "__main__":
	ELECTRIP = Fenster("ELECTRIP - Konfiguration")
	gobject.threads_init() # Möglichkeit schaffen, socket_thread auszuführen
	gtk.main()
