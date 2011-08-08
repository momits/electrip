#!/usr/bin/env python
# -*- coding: UTF 8 -*-

# Import von Modulen
try:
	import cPickle as pickle
	import gobject
	import gtk
	from Lok import Lok
	import SaveAndLoad
	print "Importe erfolgreich"
except:
	print "Es konnten nicht alle Module importiert werden"

class Fenster(gtk.Window):
	def __init__(self, titel):
		self.loks = [
		Lok(0, "Beispiellok", 5, "M 2", 27, 2.5, True, "/Pfad/zum/Bild", [{"Name": "Licht","SendeNr": 0, "Wert": True, "Button":1},{"Name": "Rangiergang", "SendeNr": 3, "Wert": False, "Button": 2}])
		]
		for lok in self.loks:
			i = 0
			for funktion in lok.funktionen:
				funktion["Nr"] = i
				i += 1
		gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
		self.set_title(titel)
		self.connect("delete-event", self.delete_event)
		self.grundbox = Grundbox(self.loks, self)
		self.add(self.grundbox)
		self.show()
		
	def delete_event(self, *args):
		gtk.main_quit()
		print "Das Programm wurde beendet."
		
class Grundbox(gtk.VBox):
	def __init__(self,loks, fenster):
		gtk.VBox.__init__(self, False, 0)
		self.hbox_mitte = HBoxMitte(loks)
		self.hbox_sonstiges = HBoxSonstiges()
		self.buttonbox_oben = Buttonbox_oben(self, self.hbox_mitte.lokliste, self.hbox_mitte.function_mapping_box, loks, self.hbox_sonstiges, fenster)


		self.pack_start(self.buttonbox_oben)
		self.pack_start(self.hbox_mitte)
		self.pack_start(self.hbox_sonstiges)
		self.show()
	
	def get_speicherdict(self):
		# Dictionary mit allen Konfigurationsdaten der Benutzeroberfläche erzeugen
		
		# 1. Erstellt eine Liste der Form <ID> <Name> <Bildpfad> <Adresse> <Protokoll> <Fahrstufen> <Fahrtrichtung (True = vorwärts)> <Beschleunigungszeit in s> <Funktionsliste {name, sende_nr, wert, Joybutton} und erzeugt daraus Lokobjekte
		liste = self.hbox_mitte.lokliste.liste
		funktionslisten = self.hbox_mitte.function_mapping_box.funktionslisten
		loks = []
		row_nr = 0
		standard_funktionsdict = ["Nr","Name","SendeNr","Wert","Button"]
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
					# dafür sorgen dass der Wert (An oder Aus) in boolean konvertiert wird:
					if eigenschaft == 'An':
						eigenschaft = True
					elif eigenschaft == 'Aus':
						eigenschaft = False
					funktion[eigenschaft_name] = eigenschaft
					nummer += 1
				funktionen.append(funktion)
			row_nr += 1
			lok.append(funktionen)
			lok_instanz = Lok(*lok)
			loks.append(lok_instanz)
			
		# 2. Serverdict der Form {"Host": host, "Port": port} erzeugen
		server = {}
		server_frame = self.hbox_sonstiges.server_frame
		i = 0
		for parameter in server_frame.parameter:
			wert = server_frame.eingabefelder[i].get_text()
			server[parameter] = wert
			i += 1
		server["Port"] = int(server["Port"])
		
		# 3. Joystickdict der Form {"Notstop": notstopbutton, "Richtungswender": wendebutton, "Achse": joyachse} erzeugen
		joystick = {}
		joy_frame = self.hbox_sonstiges.joy_frame
		i = 0
		for parameter in joy_frame.speicher_parameter:
			wert = int(joy_frame.eingabefelder[i].get_text())
			joystick[parameter] = wert
			i += 1
		# Finales Speicherdict erzeugen
		speicher_dict = {"Loks": loks, "Server": server, "Joystick": joystick}
		return speicher_dict
		

class Legendebutton(gtk.Button):
	def __init__(self):
		gtk.Button.__init__(self, "Legende...")
		self.legende = Legendefenster()
		self.connect("clicked", self.legende_zeigen)
		self.show()
		
	def legende_zeigen(self, *args):
		self.legende.show()

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
		self.begriffe = ["ID", "Lok", "Protokoll", "Fahrstufen", "Beschleunigungszeit", "Fahrtrichtung", "Bild", "Funktionsname", "SendeNr", "Wert", "JoyButton"]
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
		"Die Nummer der Funktion im Lokdecoder -> Die angesprochene Funktion",
		"Der voreingestellte Zustand der Funktion: An oder Aus",
		"Der Button am JoyStick, dem die Lokfunktion zugewiesen ist"
		]
		i = 0
		for definition in self.definitionen:
			frame = gtk.Frame(definition)
			frame.show()
			frame.set_label_align(0.0, 0.0)
			self.attach(frame, 1, 2, i, (i+1))
			i = i + 1
		self.set_col_spacing(0, 22)
		self.set_row_spacings(5)
		self.show()
				
class Ladebutton(gtk.Button):
	def __init__(self, lok_treeview, funktions_treeview, loks, hbox_sonstiges, fenster):
		self.loks = loks
		self.lok_treeview = lok_treeview
		self.funktions_treeview = funktions_treeview
		self.hbox_sonstiges = hbox_sonstiges
		
		gtk.Button.__init__(self, "Laden")
		self.connect("clicked", self.laden, fenster)
		self.show()
		
	def laden(self, *args):
		file_chooser_dialog = SaveAndLoad.DateiLadenDialog(fenster)
		try:
			letzter_pfad = pickle.load(open("electrip_configuration.conf"))
			file_chooser_dialog.set_filename(letzter_pfad)
		except:
			print "Bisher keine Standardeinstellungen gespeichert."
		response = file_chooser_dialog.run()
		if response == gtk.RESPONSE_OK:
			verzeichnis = file_chooser_dialog.get_filename()
			speicher_dict = pickle.load(open(verzeichnis))
			loks = speicher_dict["Loks"]
			server = speicher_dict["Server"]
			joystick = speicher_dict["Joystick"]
			
			self.lok_treeview.laden(loks)
			self.funktions_treeview.laden(loks)
			self.hbox_sonstiges.joy_frame.laden(joystick)
			self.hbox_sonstiges.server_frame.laden(server)
			pickle.dump(verzeichnis, open("electrip_configuration.conf", 'wb'))
			print "Einstellungen wurden aus " + verzeichnis + " geladen."
		elif response == gtk.RESPONSE_CANCEL:
			print 'Laden abgebrochen.'
		file_chooser_dialog.destroy()

class Speicherbutton(gtk.Button):
	def __init__(self, grundbox, fenster):
		gtk.Button.__init__(self, "Speichern")
		self.grundbox = grundbox
		self.connect("clicked", self.speichern, fenster)
		self.show()
		
	def speichern(self, *args):
		file_chooser_dialog = SaveAndLoad.DateiSpeichernDialog(fenster)
		try:
			letzter_pfad = pickle.load(open("electrip_configuration.conf"))
			file_chooser_dialog.set_filename(letzter_pfad)
		except:
			print "Bisher keine Standardeinstellungen gespeichert."
		response = file_chooser_dialog.run()
		if response == gtk.RESPONSE_OK:
			verzeichnis = file_chooser_dialog.get_filename()
			speicherdict = self.grundbox.get_speicherdict()
			if verzeichnis != "" and verzeichnis[len(verzeichnis)-4:len(verzeichnis)] != ".elc": # Wenn Dateiendung fehlt und ein Dateiname angegeben wurde, Endung anhängen
				verzeichnis += ".elc"
			pickle.dump(speicherdict, open(verzeichnis, 'wb'))
			pickle.dump(verzeichnis, open("electrip_configuration.conf", 'wb'))
			print "Einstellungen wurden gespeichert in " + verzeichnis
		elif response == gtk.RESPONSE_CANCEL:
			print 'Speichern abgebrochen.'
		file_chooser_dialog.destroy()

class Buttonbox_oben(gtk.HButtonBox):
	def __init__(self, grundbox, lokliste, function_mapping_box, loks, hbox_sonstiges, fenster):
		gtk.HButtonBox.__init__(self)
		self.set_layout(gtk.BUTTONBOX_START)
		self.legendebutton = Legendebutton()
		self.speicherbutton = Speicherbutton(grundbox, fenster)
		self.ladebutton = Ladebutton(lokliste, function_mapping_box, loks, hbox_sonstiges, fenster)
		
		self.add(self.legendebutton)
		self.add(self.ladebutton)
		self.add(self.speicherbutton)
		self.show()

class NeueLokButton(gtk.Button):
	def __init__(self, lokliste, funktionsbox):
		gtk.Button.__init__(self, "Neue Lok")
		self.connect("clicked", self.neue_lok, lokliste, funktionsbox)
		self.show()
		
	def neue_lok(self, button, lokliste, funktionsbox):
		funktionsbox.funktionslisten.append(gtk.ListStore(gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT))
		lokliste.append([lokliste.iter_n_children(None), None, 0 , None, 0, 3, None, None])
		
class LokLoeschenButton(gtk.Button):
	def __init__(self, lokliste, loktreeview, sort_model, funktionsbox):
		gtk.Button.__init__(self, "Lok löschen")
		self.connect("clicked", self.lok_loeschen, lokliste, loktreeview, sort_model, funktionsbox)
		self.show()
		
	def lok_loeschen(self, button, lokliste, loktreeview, sort_model, funktionsbox):
		path = loktreeview.get_cursor()[0]
		zeile = lokliste.get_iter(sort_model.convert_path_to_child_path(path)) # Zu löschende Zeile im Liststore finden: != ausgewählte Zeile im SortModel
		funktionsbox.funktionslisten.remove(funktionsbox.get_model()) # Aktuelle Funktionsliste löschen
		lokliste.remove(zeile) # Zeile im Liststore löschen

class FunktionLoeschenButton(gtk.Button):
	def __init__(self, funktionsbox):
		gtk.Button.__init__(self, "Funktion löschen")
		self.connect("clicked", self.funktion_loeschen, funktionsbox)
		self.show()
		
	def funktion_loeschen(self, button, funktionsbox):
		liste = funktionsbox.get_model() # Aktuelle Funktionsliste finden
		path = funktionsbox.get_cursor()[0]
		if path != None:
			zeile = liste.get_iter(path) # Zu löschende Zeile im Liststore finden
			liste.remove(zeile) # Zeile im Liststore löschen
		
class NeueFunktionButton(gtk.Button):
	def __init__(self, funktionsbox):
		gtk.Button.__init__(self, "Neue Funktion")
		self.connect("clicked", self.neue_funktion, funktionsbox)
		self.show()
		
	def neue_funktion(self, button, funktionsbox):
		funktionsliste = funktionsbox.get_model()
		nr = len(funktionsliste)
		funktionsliste.append([nr, None, 0, None, 0])

class Buttonbox_lokaktionen(gtk.HButtonBox):
	def __init__(self, loktreeview, lokliste, sort_model, funktionsbox):
		gtk.HButtonBox.__init__(self)
		self.set_layout(gtk.BUTTONBOX_START)
		self.neue_lok_button = NeueLokButton(lokliste, funktionsbox)
		self.lok_loeschen_button = LokLoeschenButton(lokliste, loktreeview, sort_model, funktionsbox)
		
		self.add(self.neue_lok_button)
		self.add(self.lok_loeschen_button)
		self.show()
		
class Buttonbox_funktionsaktionen(gtk.HButtonBox):
	def __init__(self, funktionsbox):
		gtk.HButtonBox.__init__(self)
		self.set_layout(gtk.BUTTONBOX_END)
		self.neue_funktion_button = NeueFunktionButton(funktionsbox)
		self.funktion_loeschen_button = FunktionLoeschenButton(funktionsbox)
		
		self.add(self.neue_funktion_button)
		self.add(self.funktion_loeschen_button)
		self.show()

class Beschriftung(gtk.Label):
	def __init__(self, text):
		gtk.Label.__init__(self)
		self.set_markup("<b>" + text + "</b>")
		self.show()

class VBoxMitte(gtk.VBox):
	def __init__(self, widget1, widget2):
		gtk.VBox.__init__(self)
		self.pack_start(widget1)
		self.pack_start(widget2, False, False)
		self.set_border_width(10)
		self.show()

class HBoxMitte(gtk.HBox):
	def __init__(self, loks):
		gtk.HBox.__init__(self)
		self.function_mapping_box = FunctionMappingBox(loks)
		self.lokliste = Lokliste(loks, self.function_mapping_box)
		self.buttonbox_lok = Buttonbox_lokaktionen(self.lokliste, self.lokliste.liste, self.lokliste.sort_model, self.function_mapping_box)
		self.buttonbox_funktionen = Buttonbox_funktionsaktionen(self.function_mapping_box)
		
		self.lok_frame = LokFrame(self.lokliste, self.buttonbox_lok)
		self.funktionen_frame = FunktionenFrame(self.function_mapping_box, self.buttonbox_funktionen)

		self.pack_start(self.lok_frame)
		self.pack_start(self.funktionen_frame)
		self.show_all()

class HBoxSonstiges(gtk.HBox):
	def __init__(self):
		gtk.HBox.__init__(self)
		self.server_frame = ServerFrame()
		self.joy_frame = JoystickFrame()
		self.pack_start(self.server_frame, False, False)
		self.pack_start(self.joy_frame, False, False)
		self.show()
		
class LokFrame(gtk.Frame):
	def __init__(self, lokliste, buttonbox):
		gtk.Frame.__init__(self)
		self.set_border_width(10) # Schönheitsabstand
		self.beschriftung = Beschriftung("Lok")
		self.set_label_widget(self.beschriftung)
		self.set_shadow_type(gtk.SHADOW_OUT)
		
		self.vbox = VBoxMitte(lokliste, buttonbox)
		self.add(self.vbox)
		self.show_all()

class FunktionenFrame(gtk.Frame):
	def __init__(self, funktionsliste, buttonbox):
		gtk.Frame.__init__(self)
		self.set_border_width(10) # Schönheitsabstand
		self.beschriftung = Beschriftung("Lokfunktionen")
		self.set_label_widget(self.beschriftung)
		self.set_shadow_type(gtk.SHADOW_OUT)
		
		self.vbox = VBoxMitte(funktionsliste, buttonbox)
		self.add(self.vbox)
		self.show_all()

		
class ServerFrame(gtk.Frame):
	def __init__(self):
		gtk.Frame.__init__(self)
		self.set_border_width(10) # Schönheitsabstand
		self.beschriftung = Beschriftung("Server")
		self.set_label_widget(self.beschriftung)
		self.set_shadow_type(gtk.SHADOW_OUT)
		self.parameter = ["Host", "Port"]
		self.eingabefelder = []
		
		self.laden({"Host": "", "Port": ""})
		self.show_all()

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
			eingabefeld.show()
			self.eingabefelder.append(eingabefeld)
			label = gtk.Label(parameter)
			label.show()
			self.table.attach(label, 0, 1, i, (i+1))
			self.table.attach(self.eingabefelder[i], 1, 2, i, (i+1))
			i += 1
		self.table.show()
		self.add(self.table)

class JoystickFrame(gtk.Frame):
	def __init__(self):
		gtk.Frame.__init__(self)
		self.set_border_width(10) # Schönheitsabstand
		self.beschriftung = Beschriftung("Joystick")
		self.set_label_widget(self.beschriftung)
		self.set_shadow_type(gtk.SHADOW_OUT)
		self.speicher_parameter = ["Notstop", "Richtungswender", "Achse"]
		self.parameter = ["Notstop (JoyButton)", "Richtungswender (JoyButton)", "Beschleunigung (JoyAchse)"] # Diese liste dient der besseren Verständlichkeit, die bei den seihcer parametern nicht so wichtig ist (und außerdem zu lang zum schreiben)
		self.eingabefelder = []
		
		self.laden({"Notstop": "", "Richtungswender": "", "Achse": ""})
		self.show_all()
		
	def laden(self, joydict):
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
		for parameter in self.speicher_parameter:
			eingabefeld = gtk.Entry()
			eingabefeld.set_text(str(joydict[parameter]))
			eingabefeld.show()
			self.eingabefelder.append(eingabefeld)
			label = gtk.Label(self.parameter[i])
			label.show()
			self.table.attach(label, i, (i+1), 0, 1)
			self.table.attach(self.eingabefelder[i], i, (i+1), 1, 2)
			i += 1
		self.table.show()
		self.add(self.table)


class FunctionMappingBox(gtk.TreeView):
	def __init__(self, loks):
		self.funktionslisten = []
		self.loks = loks
		self.laden(self.loks)
			
		# CellRenderer für Textfelder erzeugen
		self.textrenderer = gtk.CellRendererText()	
		self.textrenderer.set_property("editable", True)
		self.textrenderer.connect("editing_started", self.neue_editable)
		self.textrenderer_not_editable = gtk.CellRendererText()
		
		# CellRenderer für Combobox erzeugen
		self.comborenderer = gtk.CellRendererCombo()
		self.comborenderer.set_property("editable", True)
		self.comborenderer.set_property("text-column", 0)
		self.comborenderer.connect("editing_started", self.neue_editable)
		
		# Comborenderer aus ListStore füllen
		self.combostore_wert = gtk.ListStore(gobject.TYPE_STRING)
		self.combostore_wert.append(["An"])
		self.combostore_wert.append(["Aus"])
		self.comborenderer.set_property("model", self.combostore_wert)

		gtk.TreeView.__init__(self, self.funktionslisten[0])
		
		self.append_column(gtk.TreeViewColumn("Nr", self.textrenderer_not_editable, text = 0))
		self.append_column(gtk.TreeViewColumn("Funktionsname", self.textrenderer, text = 1))
		self.append_column(gtk.TreeViewColumn("SendeNr", self.textrenderer, text = 2))
		wertspalte = gtk.TreeViewColumn("Wert", self.comborenderer, text = 3)
		wertspalte.set_min_width(70) # Spalte verbreitern, der Schönheit wegen (Damit man auch bei der Dropdownauswahl noch was lesen kann)
		self.append_column(wertspalte)
		self.append_column(gtk.TreeViewColumn("JoyButtton", self.textrenderer, text = 4))			
		self.show()
	
	def laden(self, loks):
		del self.funktionslisten[:]
		i = 0
		self.loks = loks
		for lok in self.loks:
			self.funktionslisten.append(gtk.ListStore(gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT))
			for funktion in lok.funktionen:
				if funktion["Wert"]:
					wert = "An"
				else:
					wert = "Aus"
				self.funktionslisten[i].append([funktion["Nr"], funktion["Name"], funktion["SendeNr"], wert, funktion["Button"]])
			i = i + 1	
		
	def neue_editable(self, textrenderer, editable, path):
		editable.connect("editing-done", self.neuer_wert, path)
	
	def neuer_wert(self, editable, path):
		liste = self.get_model()
		i = 0
		for column in self.get_columns():
			if column == self.get_cursor()[1]:
				aktive_spalte = i
				spaltentyp = liste.get_column_type(i)
			else:
				i = i + 1
		zeile = liste.get_iter(path)
		try:
			neuer_text = editable.get_text()
		except:
			neuer_text = editable.get_active_text()
		print "Neuer Wert:", neuer_text
		if spaltentyp == gobject.TYPE_INT:
			liste[zeile][aktive_spalte] = int(neuer_text)
		else:
			liste[zeile][aktive_spalte] = neuer_text
		
class Lokliste(gtk.TreeView):
	def __init__(self, loks, funktionenbox):
		self.liste = gtk.ListStore(gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_FLOAT, gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.loks = loks
		self.funktionen_box = funktionenbox
		
		# CellRenderer für Textfelder erzeugen
		self.textrenderer = gtk.CellRendererText()
		self.textrenderer.set_property("editable", True)
		self.textrenderer.connect("editing_started", self.neue_editable)
		self.textrenderer_not_editable = gtk.CellRendererText()
		
		# CellRenderer-Liste für ComboBoxen erzeugen
		self.comborenderer = []
		for i in range(3): # Liste mit CellRendererCombos auffüllen
			self.comborenderer.append(gtk.CellRendererCombo())
			self.comborenderer[i].set_property("editable", True)
			self.comborenderer[i].set_property("text-column", 0)
			self.comborenderer[i].connect("editing_started", self.neue_editable)
		
		# ComboRenderer aus kleinen ListStores füllen
		# Combostore_Protokoll
		self.combostore_protokoll = gtk.ListStore(gobject.TYPE_STRING)
		self.combostore_protokoll.append(["M 1"])
		self.combostore_protokoll.append(["M 2"])
		self.combostore_protokoll.append(["N 1"])
		self.combostore_protokoll.append(["N 2"])
		self.comborenderer[0].set_property("model", self.combostore_protokoll)
		# Combostore_Fahrstufen
		self.combostore_fahrstufen = gtk.ListStore(gobject.TYPE_INT)
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
			i = i + 1
		self.laden(self.loks)
		
	def laden(self, loks):
		self.liste.clear()
		self.loks = loks
		for lok in self.loks:
			if lok.richtung:
				fahrtrichtung = "Vorwärts"
			else:
				fahrtrichtung = "Rückwärts"
			self.liste.append([lok.id, lok.name, lok.adresse, lok.protokoll, lok.fahrstufen, lok.beschleunigungszeit, fahrtrichtung, lok.bild])
		self.show()
		
	def neue_editable(self, renderer, editable, path):
		editable.connect("editing-done", self.neuer_wert, path)
	
	def neuer_wert(self, editable, path):
		i = 0
		for column in self.get_columns():
			if column == self.get_cursor()[1]:
				aktive_spalte = i
				spaltentyp = self.liste.get_column_type(i)
			else:
				i = i + 1
		zeile = self.liste.get_iter(self.sort_model.convert_path_to_child_path(path))
		try:
			neuer_text = editable.get_text()
		except:
			neuer_text = editable.get_active_text()
		print "Neuer Wert:", neuer_text
		if spaltentyp == gobject.TYPE_INT:
			self.liste[zeile][aktive_spalte] = int(neuer_text)
		elif spaltentyp == gobject.TYPE_FLOAT:
			self.liste[zeile][aktive_spalte] = float(neuer_text.replace(",",".")) # Kommas zur Umwandlung String-->Float durch Punkte ersetzen
		else:
			self.liste[zeile][aktive_spalte] = neuer_text
			

	def lokauswahl(self, treeview):
		cursor_path = self.get_cursor()[0] # Pfad zur angezeigten Zeile
		zeile = cursor_path[0]
		datenzeile = self.sort_model.convert_path_to_child_path(cursor_path)[0] #Zeile im Liststore durch Konvertierung des angezeigten Pfades in einen Liststorepfad ermitteln
		self.funktionen_box.set_model(self.funktionen_box.funktionslisten[datenzeile]) # Funktionenliste 

if __name__ == "__main__":	
	fenster = Fenster("ELECTRIP - Konfiguration")
	gtk.main()
