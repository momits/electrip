#!/usr/bin/env python
# -*- coding: utf-8 -*-
# this is ELECTRIP VERSION 2.0.2

from os import getcwd, path
package_path = path.dirname(getcwd()) # finde das parent-directory vom aktuellen working-directory

from sys import path, argv
path.append(package_path) # füge den pfad zu sys.path hinzu, damit relative Importe in den Untermodulen möglich sind

# Import von Modulen

from gi.repository import GLib, Gtk, Pango, GdkPixbuf
import cPickle as pickle
from Lok import Lok
from Constants import *
import SaveAndLoad
import ELECTRIP_Control
from LockedPrint import locked_print

class Fenster(Gtk.Window):
	def __init__(self):
		super(Fenster, self).__init__() #Gtk.WindowType.TOPLEVEL
		self.set_title("ELECTRIP " + ELECTRIP_VERSION + " Konfiguration")
		icon_list = [GdkPixbuf.Pixbuf.new_from_file(path) for path in ICON_PATH_LIST]
		self.set_icon_list(icon_list)
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
			dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, "Die Datei besitzt ungespeicherte Änderungen.\n Wollen Sie diese speichern?")
			response = dialog.run()
			dialog.destroy()
			if response == Gtk.ResponseType.YES and self.grundbox.verzeichnis == None:
				self.grundbox.buttonbox_oben.speichern_unter_button.speichern(None, self)
			elif response == Gtk.ResponseType.YES:
				speicherdict = self.grundbox.get_speicherdict()
				pickle.dump(speicherdict, open(self.grundbox.verzeichnis, 'wb'))
		if self.control_window_is_alive:
			self.steuerungsfenster.delete_event()
		Gtk.main_quit()
		locked_print("ELECTRIP wurde beendet.")
	
	def error(self, warnung):
		fehlermeldung = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, warnung)
		fehlermeldung.run()
		fehlermeldung.destroy()

class Grundbox(Gtk.VBox):
	def __init__(self, fenster, verzeichnis):
		super(Grundbox, self).__init__()
		self.has_unsaved_changes = False # Zu Beginn keine ungespeicherten Änderungen
		self.verzeichnis = verzeichnis # Zu Beginn ist keine Datei geladen
		
		self.tabbed_box = TabbedBox(fenster, self.status_changed)
		self.buttonbox_oben = ButtonboxOben(self.tabbed_box.lok_frame.scrolled_window.lok_treeview, self.tabbed_box.funktionen_frame.scrolled_window.funktion_treeview, self.tabbed_box.server_table, self.tabbed_box.joystick_table, fenster)
		
		self.pack_start(self.buttonbox_oben, False, False, 0)
		self.pack_start(self.tabbed_box, True, True, 0)
		
	def status_changed(self, widget, unsaved_changes):
		if unsaved_changes and not self.has_unsaved_changes: # wenn status gewechselt hat
			self.has_unsaved_changes = True
			if self.verzeichnis != None:
				self.buttonbox_oben.speicherbutton.set_sensitive(True)
			locked_print("Widget '" + unicode(widget) + u"' meldet ungespeicherte Änderungen.")
		elif not unsaved_changes and self.has_unsaved_changes:
			self.has_unsaved_changes = False
			self.buttonbox_oben.speicherbutton.set_sensitive(False)
	
	def get_speicherdict(self):
		# Dictionary mit allen Konfigurationsdaten der Benutzeroberfläche erzeugen
		
		# 1. Erstellt eine Liste der Form <ID> <Name> <Bildpfad> <Adresse> <Protokoll> <Fahrstufen> <Fahrtrichtung (True = vorwärts)> <Beschleunigungszeit in s> <Funktionsliste {name, sende_nr, wert, Joybutton} und erzeugt daraus Lokobjekte
		liste = self.tabbed_box.lok_frame.scrolled_window.lok_treeview.liste
		funktionslisten = self.tabbed_box.funktionen_frame.scrolled_window.funktion_treeview.funktionslisten
		loks = []
		row_nr = 0
		for row in liste:
			lok = []
			funktionen = []
			nummer = 0
			for eigenschaft in row:
				# dafür sorgen dass die Fahrtrichtung in boolean konvertiert wird:
				if unicode(eigenschaft) == u'Vorwärts':
					eigenschaft = True
				elif unicode(eigenschaft) == u'Rückwärts':
					eigenschaft = False
				lok.append(eigenschaft)
				nummer += 1

			for row in funktionslisten[row_nr]:
				funktion = {}
				nummer = 0
				for eigenschaft in row:
					eigenschaft_name = CONFIG_LOCO_FUNCTION_PARAMETERS[nummer]
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
		server_table = self.tabbed_box.server_table
		i = 0
		for parameter in CONFIG_SERVER_PARAMETERS_SHORT:
			wert = server_table.eingabefelder[i].get_text()
			server[parameter] = wert
			i += 1
		try:
			server["Port"] = int(server["Port"])
		except ValueError:
			locked_print(u"Server-Parameter Port ist nicht gültig.")
			server["Port"] = "" # Setze Server-Port auf leer, weil Angabe unkorrekt
			
		# 3. Joystickdict der Form {"Notstop": notstopbutton, "Richtungswender": wendebutton, "Achse": joyachse} erzeugen
		joystick = {}
		joystick_table = self.tabbed_box.joystick_table
		i = 0
		for parameter in CONFIG_JOYSTICK_PARAMETERS_SHORT:
			try:
				wert = joystick_table.eingabefelder[i].get_text()
				wert = int(wert)
				joystick[parameter] = wert
			except ValueError:
				locked_print("Joystick-Parameter", parameter, u"ist nicht gültig.")
				joystick[parameter] = "" # Setze Parameter auf leer, weil Angabe unkorrekt
			i += 1
		
		# Finales Speicherdict erzeugen
		speicher_dict = {"Loks": loks, "Server": server, "Joystick": joystick}
		return speicher_dict

class StockBildButton(Gtk.Button):
	def __init__(self, label, stock):
		super(StockBildButton, self).__init__()
		icon = Gtk.Image()
		icon.set_from_stock(stock, Gtk.IconSize.BUTTON)
		label = Gtk.Label(label=label)
		hbox = Gtk.HBox(False, 5)
		hbox.pack_start(label, True, True, 0)
		hbox.pack_start(icon, True, True, 0)
		self.add(hbox)

class Ladebutton(StockBildButton):
	def __init__(self, lok_treeview, funktions_treeview, server_table, joystick_table, fenster):
		StockBildButton.__init__(self, "Laden", Gtk.STOCK_OPEN)
		self.lok_treeview = lok_treeview
		self.funktions_treeview = funktions_treeview
		self.server_table = server_table
		self.joystick_table = joystick_table
		
		self.connect("clicked", self.lade_dialog, fenster)
		
	def lade_dialog(self, button, fenster):
		file_chooser_dialog = SaveAndLoad.DateiLadenDialog(fenster)
		try:
			letzter_pfad = pickle.load(open("electrip.conf"))
			file_chooser_dialog.set_filename(letzter_pfad)
		except IOError:
			locked_print("Bisher keine Standardeinstellungen gespeichert.")
		response = file_chooser_dialog.run()
		if response == Gtk.ResponseType.OK:
			verzeichnis = file_chooser_dialog.get_filename()
			self.laden(verzeichnis, fenster)
			fenster.show_all()
		elif response == Gtk.ResponseType.CANCEL:
			locked_print('Laden abgebrochen.')
		file_chooser_dialog.destroy()
		
	def laden(self, verzeichnis, fenster):
		try:
			speicher_dict = pickle.load(open(verzeichnis))
			loks = speicher_dict["Loks"]
			server = speicher_dict["Server"]
			joystick = speicher_dict["Joystick"]
			self.lok_treeview.laden(loks) # loks
			self.funktions_treeview.laden(loks) # loks
			self.joystick_table.laden(joystick) # joystick
			self.server_table.laden(server) # server
			pickle.dump(verzeichnis, open("electrip.conf", 'wb'))
			fenster.grundbox.verzeichnis = verzeichnis
			fenster.grundbox.status_changed(None, False)
			locked_print("Einstellungen wurden aus " + verzeichnis + " geladen.")
			fenster.set_title("ELECTRIP " + ELECTRIP_VERSION + " Konfiguration - " + verzeichnis)
			return True
		except IOError:
			fenster.error(u"Der Dateipfad ist ungültig! Konnte Konfiguration nicht laden.")
			return False
		except:
			fenster.error(u"Laden gescheitert.\nEs handelt sich um keine gültige ELECTRIP-Datei.")
			return False

class SpeichernUnterButton(StockBildButton):
	def __init__(self, fenster):
		StockBildButton.__init__(self, "Speichern unter", Gtk.STOCK_SAVE_AS)
		self.connect("clicked", self.speichern, fenster)
		
	def speichern(self, button, fenster):
		file_chooser_dialog = SaveAndLoad.DateiSpeichernDialog(fenster)
		if fenster.grundbox.verzeichnis == None:
			try:
				letzter_pfad = pickle.load(open("electrip.conf"))
				file_chooser_dialog.set_filename(letzter_pfad)
			except:
				locked_print("Bisher keine Standardeinstellungen gespeichert.")
		else:
			file_chooser_dialog.set_filename(fenster.grundbox.verzeichnis)
		response = file_chooser_dialog.run()
		if response == Gtk.ResponseType.OK:
			verzeichnis = file_chooser_dialog.get_filename()
			speicherdict = fenster.grundbox.get_speicherdict()
			if verzeichnis != "" and verzeichnis[len(verzeichnis)-4:len(verzeichnis)] != ".elc": # Wenn Dateiendung fehlt und ein Dateiname angegeben wurde, Endung anhängen
				verzeichnis += ".elc"
			pickle.dump(speicherdict, open(verzeichnis, 'wb'))
			pickle.dump(verzeichnis, open("electrip.conf", 'wb'))
			locked_print("Einstellungen wurden gespeichert in " + verzeichnis)
			fenster.set_title("ELECTRIP " + ELECTRIP_VERSION + " Konfiguration - " + verzeichnis)
			fenster.grundbox.verzeichnis = verzeichnis
			fenster.grundbox.status_changed(None, False)
		elif response == Gtk.ResponseType.CANCEL:
			locked_print('Speichern abgebrochen.')
		file_chooser_dialog.destroy()

class SpeicherButton(StockBildButton):
	def __init__(self, fenster):
		StockBildButton.__init__(self, "Speichern", Gtk.STOCK_SAVE)
		self.connect("clicked", self.speichern, fenster)
		self.set_sensitive(False)
		
	def speichern(self, button, fenster):
		speicherdict = fenster.grundbox.get_speicherdict()
		pickle.dump(speicherdict, open(fenster.grundbox.verzeichnis, 'wb'))
		fenster.grundbox.status_changed(None, False)

class ElectripLadebutton(StockBildButton):
	def __init__(self, fenster):
		StockBildButton.__init__(self, "In ELECTRIP-Steuerung laden", Gtk.STOCK_EXECUTE)
		self.connect("clicked", self.in_electrip_laden, fenster)
		fenster.steuerungsfenster = None
	
	def in_electrip_laden(self, button, fenster):
		fenster.hide()
		if fenster.steuerungsfenster != None:
			fenster.steuerungsfenster.delete_event(show_config_fenster=False) # Alte Steuerung beenden und danach nicht das Konfigurationsfenster einblenden, sondern ein neues Steuerungsfenster starten
		fenster.steuerungsfenster = ELECTRIP = ELECTRIP_Control.Fenster(fenster)

class ButtonboxOben(Gtk.HBox):
	def __init__(self, lok_treeview, funktion_treeview, server_table, joystick_table, fenster):
		super(ButtonboxOben, self).__init__()
		self.ladebutton = Ladebutton(lok_treeview, funktion_treeview, server_table, joystick_table, fenster)
		self.speichern_unter_button = SpeichernUnterButton(fenster)
		self.speicherbutton = SpeicherButton(fenster)
		self.electrip_ladebutton = ElectripLadebutton(fenster)

		self.pack_start(self.ladebutton, False, False, 0)
		self.pack_start(self.speichern_unter_button, False, False, 0)
		self.pack_start(self.speicherbutton, False, False, 0)
		self.pack_start(self.electrip_ladebutton, False, False, 0)

class NeueLokButton(Gtk.Button):
	def __init__(self, lok_treeview, funktion_treeview, save_status_method):
		super(NeueLokButton, self).__init__(self, "Neue Lok")
		self.connect("clicked", self.neue_lok, lok_treeview, funktion_treeview, save_status_method)
		
	def neue_lok(self, button, lok_treeview, funktion_treeview, save_status_method):
		path = lok_treeview.get_cursor()[0]
		if path == None:		
			funktion_treeview.funktionslisten.append(Gtk.ListStore(*CONFIG_FUNCTION_TREEVIEW_COLUMN_TYPES))
			nr = len(lok_treeview.liste)
			werte = CONFIG_LOCO_STANDARD_VALUES
			werte[0] = nr
			lok_treeview.liste.append(werte)
		else: # Wenn eine Zeile ausgewählt, dann füge Lok unterhalb dieser Zeile ein
			zeile = lok_treeview.liste.get_iter(path)
			zeile_nr = path.get_indices()[0]
			neue_zeile = lok_treeview.liste.insert_after(zeile, CONFIG_LOCO_STANDARD_VALUES) # Nach der ausgewählten Zeile eine neue Zeile mit Standardwerten einfügen
			funktion_treeview.funktionslisten.insert(zeile_nr + 1, Gtk.ListStore(*CONFIG_FUNCTION_TREEVIEW_COLUMN_TYPES)) # In der Liste der Funktionen-Liststores einen neuen Liststore einfügen
			lok_treeview.nummerieren() # Lok-ID's in die richtige Reihenfolge bringen
			lok_treeview.set_cursor(lok_treeview.liste.get_path(neue_zeile), None, False)
		save_status_method("NeueLokButton", True)

class LokLoeschenButton(Gtk.Button):
	def __init__(self, lok_treeview, funktion_treeview, save_status_method):
		super(LokLoeschenButton, self).__init__("Lok löschen")
		self.connect("clicked", self.lok_loeschen, lok_treeview, funktion_treeview, save_status_method)
		
	def lok_loeschen(self, button, lok_treeview, funktion_treeview, save_status_method):
		try:
			path = lok_treeview.get_cursor()[0]
			zeile = lok_treeview.liste.get_iter(path) # Zu löschende Zeile im Liststore finden: != ausgewählte Zeile im SortModel
			
			liststore = funktion_treeview.get_model()
			funktion_treeview.funktionslisten.remove(liststore) # Aktuelle Funktionsliste löschen
			
			lok_treeview.liste.remove(zeile) # Zeile im Liststore löschen
			lok_treeview.nummerieren()
			
			lok_treeview.set_cursor(path, None, False) # wähle selbe zeile wieder aus, damit viele loks auf einmal gelöscht werden können
				
			save_status_method("LokLoeschenButton", True)
		except TypeError:
			locked_print(u"Keine Zeile ausgewählt.")

class NeueFunktionButton(Gtk.Button):
	def __init__(self, funktion_treeview, save_status_method):
		super(NeueFunktionButton, self).__init__("Neue Funktion")
		self.connect("clicked", self.neue_funktion, funktion_treeview, save_status_method)
		
	def neue_funktion(self, button, funktion_treeview, save_status_method):
		try:
			funktionsliste = funktion_treeview.get_model()
			nr = len(funktionsliste)
			werte = CONFIG_LOCO_FUNCTION_STANDARD_VALUES
			werte[0] = nr
			funktionsliste.append(werte)
			save_status_method("NeueFunktionButton", True)
		except TypeError:
			locked_print(u"Keine Lok ausgewählt.")
			
class FunktionLoeschenButton(Gtk.Button):
	def __init__(self, funktion_treeview, save_status_method):
		super(FunktionLoeschenButton, self).__init__("Funktion löschen")
		self.connect("clicked", self.funktion_loeschen, funktion_treeview, save_status_method)
		
	def funktion_loeschen(self, button, funktion_treeview, save_status_method):
		liste = funktion_treeview.get_model() # Aktuelle Funktionsliste finden
		path = funktion_treeview.get_cursor()[0]
		if path != None:
			zeile = liste.get_iter(path) # Zu löschende Zeile im Liststore finden
			liste.remove(zeile) # Zeile im Liststore löschen
			funktion_treeview.nummerieren()
			save_status_method("FunktionLoeschenButton", True)
			
class ArrowButton(Gtk.Button):
	def __init__(self, direction): # direction: True = nach oben
		super(ArrowButton, self).__init__()
		self.direction = direction
		if direction:
			self.set_image(Gtk.Arrow.new(Gtk.ArrowType.UP, Gtk.ShadowType.NONE))
		else:
			self.set_image(Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.NONE))

class ButtonboxLokAktionen(Gtk.HButtonBox):
	def __init__(self, lok_treeview, funktion_treeview, save_status_method):
		super(ButtonboxLokAktionen, self).__init__()
		self.set_layout(Gtk.ButtonBoxStyle.START)
		self.neue_lok_button = NeueLokButton(lok_treeview, funktion_treeview, save_status_method)
		self.lok_loeschen_button = LokLoeschenButton(lok_treeview, funktion_treeview, save_status_method)
		self.move_up_button = ArrowButton(True)
		self.move_up_button.connect("clicked", self.clicked, lok_treeview, funktion_treeview, save_status_method)
		self.move_down_button = ArrowButton(False)
		self.move_down_button.connect("clicked", self.clicked, lok_treeview, funktion_treeview, save_status_method)
		
		self.add(self.neue_lok_button)
		self.add(self.lok_loeschen_button)
		self.add(self.move_up_button)
		self.add(self.move_down_button)

	def clicked(self, button, lok_treeview, funktion_treeview, save_status_method):
		try:
			path, column = lok_treeview.get_cursor()
			zeile = lok_treeview.liste.get_iter(path)
			zeile_nr = path.get_indices()[0]
			if button.direction and zeile_nr > 0: # wenn verschiebe-richtung nach oben und zeile nicht ganz oben steht
				zeile_davor = lok_treeview.liste.iter_nth_child(None, zeile_nr -1)
				funktion_treeview.funktionslisten.insert(zeile_nr-1, funktion_treeview.funktionslisten.pop(zeile_nr)) # Funktionen-Liststore an andere Stelle setzen
				lok_treeview.liste.move_before(zeile, zeile_davor)
				lok_treeview.liste.set_value(zeile_davor, 0, zeile_nr)
				lok_treeview.liste.set_value(zeile, 0, zeile_nr-1)
				lok_treeview.set_cursor(Gtk.TreePath.new_from_string(str(zeile_nr-1)), None, False)
				save_status_method("MoveUpButton - Lok", True)
			elif not button.direction and zeile_nr < len(lok_treeview.liste)-1:
				zeile_danach = lok_treeview.liste.iter_nth_child(None, zeile_nr + 1)
				funktion_treeview.funktionslisten.insert(zeile_nr+1, funktion_treeview.funktionslisten.pop(zeile_nr)) # Funktionen-Liststore an andere Stelle setzen
				lok_treeview.liste.move_after(zeile, zeile_danach)
				lok_treeview.liste.set_value(zeile_danach, 0, zeile_nr)
				lok_treeview.liste.set_value(zeile, 0, zeile_nr+1)
				lok_treeview.set_cursor(Gtk.TreePath.new_from_string(str(zeile_nr+1)), None, False)
				save_status_method("MoveDownButton - Lok", True)
			else:
				locked_print("Lok befindet sich schon am Rand, kann nicht weiter verschoben werden.")
		except TypeError:
			locked_print(u"Es ist keine Lok ausgewählt, es kann nichts verschoben werden.")

class ButtonboxFunktionAktionen(Gtk.HButtonBox):
	def __init__(self, funktion_treeview, save_status_method):
		super(ButtonboxFunktionAktionen, self).__init__()
		self.set_layout(Gtk.ButtonBoxStyle.START)
		self.neue_funktion_button = NeueFunktionButton(funktion_treeview, save_status_method)
		self.funktion_loeschen_button = FunktionLoeschenButton(funktion_treeview, save_status_method)
		self.move_up_button = ArrowButton(True)
		self.move_up_button.connect("clicked", self.clicked, funktion_treeview, save_status_method)
		self.move_down_button = ArrowButton(False)
		self.move_down_button.connect("clicked", self.clicked, funktion_treeview, save_status_method)
		
		self.add(self.neue_funktion_button)
		self.add(self.funktion_loeschen_button)
		self.add(self.move_up_button)
		self.add(self.move_down_button)
	
	def clicked(self, button, funktion_treeview, save_status_method):
		try:
			liste = funktion_treeview.get_model()
			path, column = funktion_treeview.get_cursor()
			zeile = liste.get_iter(path)
			zeile_nr = path.get_indices()[0]
			if button.direction and zeile_nr > 0: # wenn verschiebe-richtung nach oben und zeile nicht ganz oben steht
				zeile_davor = liste.iter_nth_child(None, zeile_nr -1)
				liste.move_before(zeile, zeile_davor)
				liste.set_value(zeile_davor, 0, zeile_nr)
				liste.set_value(zeile, 0, zeile_nr-1)
				funktion_treeview.set_cursor(Gtk.TreePath.new_from_string(str(zeile_nr-1)), None, False)
				save_status_method("MoveUpButton - Funktion", True)
			elif not button.direction and zeile_nr < len(liste)-1:
				zeile_danach = liste.iter_nth_child(None, zeile_nr + 1)
				liste.move_after(zeile, zeile_danach)
				liste.set_value(zeile_danach, 0, zeile_nr)
				liste.set_value(zeile, 0, zeile_nr+1)
				funktion_treeview.set_cursor(Gtk.TreePath.new_from_string(str(zeile_nr+1)), None, False)
				save_status_method("MoveDownButton - Funktion", True)
			else:
				locked_print("Funktion befindet sich schon am Rand, kann nicht weiter verschoben werden.")
		except AttributeError:
			locked_print(u"Keine Lok (und damit keine Funktion) ausgewählt, es kann nichts verschoben werden.")
		except TypeError:
			locked_print(u"Es ist keine Funktion ausgewählt, es kann nichts verschoben werden.")

class Beschriftung(Gtk.Label):
	def __init__(self, text):
		super(Beschriftung, self).__init__()
		self.set_markup("<b>" + text + "</b>")

class TopAlignment(Gtk.Alignment):
	def __init__(self, child):
		super(TopAlignment, self).__init__()
		self.set(0.0, 0.0, 0.0, 0.0)
		self.add(child)

class TabbedBox(Gtk.Notebook):
	def __init__(self, fenster, save_status_method):
		super(TabbedBox, self).__init__()
		self.hbox_lok = Gtk.HBox()
		self.funktionen_frame = FunktionenFrame(save_status_method)
		self.lok_frame = LokFrame(self.funktionen_frame.scrolled_window.funktion_treeview, fenster, save_status_method)
		self.hbox_lok.pack_start(self.lok_frame, True, True, 0)
		self.hbox_lok.pack_start(self.funktionen_frame, False, False, 0)
		self.append_page(self.hbox_lok, Gtk.Label(label="Lokomotiven"))
		
		self.server_table = ServerTable(save_status_method)
		self.append_page(TopAlignment(self.server_table), Gtk.Label(label="SRCP-Server"))
		
		self.joystick_table = JoystickTable(save_status_method)
		self.append_page(TopAlignment(self.joystick_table), Gtk.Label(label="Joystick / Gamepad"))
		

class FunktionenFrame(Gtk.Frame):
	def __init__(self, save_status_method):
		super(FunktionenFrame, self).__init__()
		self.set_border_width(10) # Schönheitsabstand
		beschriftung = Beschriftung("Funktionen der Lokomotive")
		self.set_label_widget(beschriftung)
		self.set_shadow_type(Gtk.ShadowType.OUT)
				
		self.scrolled_window = ScrolledWindowFunktionen(save_status_method)
		self.buttonbox_funktionen = ButtonboxFunktionAktionen(self.scrolled_window.funktion_treeview, save_status_method)
		
		vbox = Gtk.VBox()
		vbox.pack_start(self.scrolled_window, True, True, 0)
		vbox.pack_start(self.buttonbox_funktionen, False, False, 0)
		self.add(vbox)

class ScrolledWindowFunktionen(Gtk.ScrolledWindow):
	def __init__(self, save_status_method):
		super(ScrolledWindowFunktionen, self).__init__()
		self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.funktion_treeview = FunktionTreeView(save_status_method)
		min_req, natural_req = self.funktion_treeview.get_preferred_size()
		self.set_size_request(natural_req.width, natural_req.height+40)
		self.add(self.funktion_treeview)
		
class LokFrame(Gtk.Frame):
	def __init__(self, funktion_treeview, fenster, save_status_method):
		super(LokFrame, self).__init__()
		self.set_border_width(10) # Schönheitsabstand
		beschriftung = Beschriftung("Allgemeine Eigenschaften")
		self.set_label_widget(beschriftung)
		self.set_shadow_type(Gtk.ShadowType.OUT)
		
		self.scrolled_window = ScrolledWindowLok(funktion_treeview, fenster, save_status_method)
		self.buttonbox_lok = ButtonboxLokAktionen(self.scrolled_window.lok_treeview, funktion_treeview, save_status_method)
		
		vbox = Gtk.VBox()
		vbox.pack_start(self.scrolled_window, True, True, 0)
		vbox.pack_start(self.buttonbox_lok, False, False, 0)
		self.add(vbox)

class ScrolledWindowLok(Gtk.ScrolledWindow):
	def __init__(self, funktion_treeview, fenster, save_status_method):
		super(Gtk.ScrolledWindow, self).__init__()
		self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.lok_treeview = LokTreeView(funktion_treeview, fenster, save_status_method)
		req_min, req_natural = self.lok_treeview.get_preferred_size()
		self.set_size_request(req_natural.width, req_natural.height+40)
		self.add(self.lok_treeview)
		
class ServerTable(Gtk.Table):
	def __init__(self, save_status_method):
		super(ServerTable, self).__init__(len(CONFIG_SERVER_PARAMETERS), 3)
		self.set_col_spacings(10)
		self.set_row_spacings(5)
		self.set_border_width(6) # Schönheitsabstand
		self.eingabefelder = []
		y = 0
		for parameter, definition in CONFIG_SERVER_PARAMETERS:
			eingabefeld = Gtk.Entry()
			eingabefeld.connect("changed", save_status_method, True)
			parameter_label = Beschriftung(parameter)
			definition_label = Gtk.Label(label=definition)
			definition_label.set_alignment(0, 0.5)
			self.attach(parameter_label, 0, 1, y, y+1)
			self.attach(eingabefeld, 1, 2, y, y+1)
			self.attach(definition_label, 2, 3, y , y+1)
			self.eingabefelder.append(eingabefeld)
			y += 1
		
	def laden(self, joydict):
		i = 0
		for parameter in CONFIG_SERVER_PARAMETERS_SHORT:
			self.eingabefelder[i].set_text(str(joydict[parameter]))
			i += 1

class JoystickTable(Gtk.Table):
	def __init__(self, save_status_method):
		super(JoystickTable, self).__init__(len(CONFIG_JOYSTICK_PARAMETERS), 3)
		self.set_col_spacings(10)
		self.set_row_spacings(5)
		self.set_border_width(6) # Schönheitsabstand
		self.eingabefelder = []
		y = 0
		for parameter, definition in CONFIG_JOYSTICK_PARAMETERS:
			eingabefeld = Gtk.Entry()
			eingabefeld.connect("changed", save_status_method, True)
			parameter_label = Beschriftung(parameter)
			definition_label = Gtk.Label(label=definition)
			definition_label.set_alignment(0, 0.5)
			self.attach(parameter_label, 0, 1, y, y+1)
			self.attach(eingabefeld, 1, 2, y, y+1)
			self.attach(definition_label, 2, 3, y , y+1)
			self.eingabefelder.append(eingabefeld)
			y += 1
		
	def laden(self, joydict):
		i = 0
		for parameter in CONFIG_JOYSTICK_PARAMETERS_SHORT:
			self.eingabefelder[i].set_text(str(joydict[parameter]))
			i += 1

class FunktionTreeView(Gtk.TreeView):
	def __init__(self, save_status_method):
		self.funktionslisten = []
		self.save_status_method = save_status_method
		self.cell_renderers = []
			
		# CellRenderer für Textfelder erzeugen
		textrenderer = Gtk.CellRendererText()	
		textrenderer.set_property("editable", True)
		textrenderer.set_property("ellipsize", Pango.EllipsizeMode.END)
		textrenderer.connect("edited", self.neuer_wert)
		self.cell_renderers.append(textrenderer)
		# CellRenderer für nicht editierbare Textfelder erzeugen
		textrenderer_not_editable = Gtk.CellRendererText()
		self.cell_renderers.append(textrenderer_not_editable)
		
		# CellRenderer für Combobox erzeugen
		for i in range(2): # Liste mit CellRendererCombos auffüllen
			comborenderer = Gtk.CellRendererCombo()
			comborenderer.set_property("editable", True)
			comborenderer.set_property("has-entry", False)
			comborenderer.set_property("text-column", 0)
			comborenderer.connect("edited", self.neuer_wert)
			self.cell_renderers.append(comborenderer)
		
		# Comborenderer 0 aus ListStore für Wert füllen
		combostore_wert = Gtk.ListStore(GObject.TYPE_STRING)
		combostore_wert.append(["An"])
		combostore_wert.append(["Aus"])
		self.cell_renderers[2].set_property("model", combostore_wert)
		
		# Comborenderer 1 aus ListStore für Taster füllen
		combostore_taster = Gtk.ListStore(GObject.TYPE_STRING)
		combostore_taster.append(["Taster"])
		combostore_taster.append(["Umschalter"])
		self.cell_renderers[3].set_property("model", combostore_taster)		

		super(FunktionTreeView, self).__init__()
		
		nr = 0
		for column_name, column_tooltip, renderer_id in CONFIG_FUNCTION_COLUMN_NAMES_TOOLTIPS_RENDERERS:
			label = Gtk.Label(label=column_name)
			label.show()
			label.set_tooltip_text(column_tooltip)
			column = Gtk.TreeViewColumn(None, self.cell_renderers[renderer_id], text = nr)
			column.set_widget(label)
			column.set_resizable(True) # Spalten vergrößerbar / verkleinerbar machen
			column.set_data("colnr", nr) # Versehe jede Spalte mit einer Nummer, zur leichten Identifizierung
			self.append_column(column)
			nr += 1
	
	def laden(self, loks):
		del self.funktionslisten[:]
		i = 0
		for lok in loks:
			self.funktionslisten.append(Gtk.ListStore(*CONFIG_FUNCTION_TREEVIEW_COLUMN_TYPES))
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
			i += 1
		
	def nummerieren(self):
		liste = self.get_model()
		id = 0
		for row in liste:
			row[0] = id
			id += 1
	
	def neuer_wert(self, editable, path, text = None):
		liste = self.get_model()
		column_nr = self.get_cursor()[1].get_data("colnr")
		
		if text == None:
			try:
				neuer_text = editable.get_text()
			except:
				neuer_text = editable.get_active_text()
		else:
			neuer_text = text
		
		if CONFIG_FUNCTION_TREEVIEW_COLUMN_TYPES[column_nr] == GObject.TYPE_INT:
			try:
				liste[path][column_nr] = int(neuer_text)
			except ValueError:
				locked_print("Falsche Eingabe, Sie haben keinen Wert eingegeben, der in den Typ Integer umgewandelt werden kann.")
		else:
			liste[path][column_nr] = neuer_text
		self.save_status_method("FunktionTreeView", True)

class LokTreeView(Gtk.TreeView):
	def __init__(self, funktion_treeview, fenster, save_status_method):
		self.liste = Gtk.ListStore(*CONFIG_LOCO_TREEVIEW_COLUMN_TYPES)
		self.save_status_method = save_status_method
		self.cell_renderers = [] # Liste, in der alle cellrenderer abegelegt werden
		
		# CellRenderer für Textfelder erzeugen
		textrenderer = Gtk.CellRendererText()
		textrenderer.set_property("editable", True)
		textrenderer.set_property("ellipsize", Pango.EllipsizeMode.END)
		textrenderer.connect("edited", self.neuer_wert)
		self.cell_renderers.append(textrenderer)
		
		textrenderer_not_editable = Gtk.CellRendererText()
		textrenderer_not_editable.set_property("ellipsize", Pango.EllipsizeMode.END)
		self.cell_renderers.append(textrenderer_not_editable)
		
		# CellRenderer-Liste für ComboBoxen erzeugen
		#self.comborenderer = []
		for i in range(3): # Liste mit CellRendererCombos auffüllen
			comborenderer = Gtk.CellRendererCombo()
			comborenderer.set_property("editable", True)
			comborenderer.set_property("text-column", 0)
			comborenderer.set_property("has-entry", False)
			comborenderer.connect("edited", self.neuer_wert)
			self.cell_renderers.append(comborenderer)
		
		# ComboRenderer aus kleinen ListStores füllen
		# Combostore_Protokoll
		combostore_protokoll = Gtk.ListStore(GObject.TYPE_STRING)
		combostore_protokoll.append(["M 1"])
		combostore_protokoll.append(["M 2"])
		combostore_protokoll.append(["N 1"])
		combostore_protokoll.append(["N 2"])
		self.cell_renderers[2].set_property("model", combostore_protokoll)
		# Combostore_Fahrstufen
		combostore_fahrstufen = Gtk.ListStore(GObject.TYPE_INT) # Für CellRendererCombo muss Type String sein, sonst segfault!
		combostore_fahrstufen.append([14])
		combostore_fahrstufen.append([27])
		combostore_fahrstufen.append([28])
		combostore_fahrstufen.append([128])
		self.cell_renderers[3].set_property("model", combostore_fahrstufen)
		# Combostore_Fahrtrichtung
		combostore_fahrtrichtung = Gtk.ListStore(GObject.TYPE_STRING)
		combostore_fahrtrichtung.append(["Vorwärts"])
		combostore_fahrtrichtung.append(["Rückwärts"])
		self.cell_renderers[4].set_property("model", combostore_fahrtrichtung)
		
		# SortModel erstellen: Verbindung zwischen angezeigter und gespeicherter Datenreihenfolge
		super(LokTreeView, self).__init__(self.liste)
		self.connect("cursor-changed", self.lok_auswahl, funktion_treeview)
		self.connect("row-activated", self.bild_auswahl, fenster)
		
		# Spalten hinzufügen
		nr = 0
		for column_name, column_tooltip, renderer_id in CONFIG_LOCO_COLUMN_NAMES_TOOLTIPS_RENDERERS:
			label = Gtk.Label(label=column_name)
			label.show()
			label.set_tooltip_text(column_tooltip)
			column = Gtk.TreeViewColumn(None, self.cell_renderers[renderer_id], text = nr)
			column.set_widget(label)
			column.set_resizable(True) # Spalten vergrößerbar / verkleinerbar machen
			column.set_data("colnr", nr) # Versehe jede Spalte mit einer Nummer, zur leichten Identifizierung
			self.append_column(column)
			nr += 1
		
	def laden(self, loks):
		self.liste.clear()
		self.loks = loks
		for lok in self.loks:
			if lok.richtung:
				fahrtrichtung = "Vorwärts"
			else:
				fahrtrichtung = "Rückwärts"
			if lok.bild == None: #########################################################################################################
				lok.bild = "" # Kompatibilität mit altem Dateiformat
			self.liste.append([lok.id, lok.name, lok.adresse, lok.protokoll, lok.fahrstufen, lok.beschleunigungszeit, fahrtrichtung, lok.bild])
	
	def nummerieren(self):
		id = 0
		for row in self.liste:
			row[0] = id
			id += 1
	
	def neuer_wert(self, cellrenderer, path, neuer_text): # neuer_text = None
		path, column = self.get_cursor()
		column_nr = column.get_data("colnr") # Rufe zugewiesene Eigenschaft "colnr" auf (siehe oben -> 'set_data')

		if CONFIG_LOCO_TREEVIEW_COLUMN_TYPES[column_nr] == GObject.TYPE_INT:
			try:
				self.liste[path][column_nr] = int(neuer_text)
			except ValueError:
				locked_print("Falsche Eingabe, Sie haben keinen Wert eingegeben, der in den Typ Integer umgewandelt werden kann.")
		elif CONFIG_LOCO_TREEVIEW_COLUMN_TYPES[column_nr] == GObject.TYPE_FLOAT:
			try:
				self.liste[zeile][column_nr] = float(neuer_text.replace(",",".")) # Kommas zur Umwandlung String-->Float durch Punkte ersetzen
			except ValueError:
				locked_print("Falsche Eingabe: Sie haben keinen Wert eingegeben, der in den Typ Float umgewandelt werden kann.")
		else:
			self.liste[path][column_nr] = neuer_text
		self.save_status_method("LokTreeView", True)

	def lok_auswahl(self, treeview, funktion_treeview):
		path, column = self.get_cursor()
		if path == None:
			funktion_treeview.set_model(None)
		else:
			zeile = path.get_indices()[0]
			funktion_treeview.set_model(funktion_treeview.funktionslisten[zeile]) # Zugehörige Funktionenliste auswählen
			
	def bild_auswahl(self, treeview, path, column, fenster):
		column_nr = column.get_data("colnr") # Rufe zugewiesene Eigenschaft "colnr" auf (siehe oben -> 'set_data')
		if column_nr == CONFIG_PICTURE_COLUMN: # wenn bildspalte ausgewählt, starte filechooser-dialog
			file_chooser_dialog = SaveAndLoad.BildLadenDialog(fenster)
			response = file_chooser_dialog.run()
			if response == Gtk.ResponseType.OK:
				verzeichnis = file_chooser_dialog.get_filename()
				self.liste.set_value(self.liste.get_iter(path), column_nr, verzeichnis)
			elif response == Gtk.ResponseType.CANCEL:
				locked_print('Laden abgebrochen.')
			file_chooser_dialog.destroy()
		fenster.grundbox.status_changed("LokTreeView", True)

if __name__ == "__main__":
	ELECTRIP = Fenster()
	GLib.threads_init() # Möglichkeit schaffen, socket_thread auszuführen
	Gtk.main()
