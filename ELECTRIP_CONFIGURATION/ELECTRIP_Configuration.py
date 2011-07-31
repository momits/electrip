#!/usr/bin/env python
# -*- coding: UTF 8 -*-

# Import von Modulen
try:
	import cPickle as pickle
	import gobject
	import gtk
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
		self.grundbox = Grundbox(self.loks)
		self.add(self.grundbox)
		self.show()
		
	def delete_event(self, *args):
		gtk.main_quit()
		print "Das Programm wurde beendet."
		
class Grundbox(gtk.VBox):
	def __init__(self,loks):
		gtk.VBox.__init__(self, False, 0)
		self.hbox_mitte = HBoxMitte(loks)
		self.buttonbox_oben = Buttonbox_oben(self, self.hbox_mitte.lokliste, self.hbox_mitte.function_mapping_box, loks)
		self.hbox_unten = HBoxUnten(self.hbox_mitte.lokliste, self.hbox_mitte.lokliste.liste,self.hbox_mitte.lokliste.sort_model, self.hbox_mitte.function_mapping_box)

		self.pack_start(self.buttonbox_oben)
		self.pack_start(self.hbox_mitte)
		self.pack_start(self.hbox_unten)
		self.show()
	
	def get_lokliste(self):
		# Erstellt eine Liste der Form <ID> <Name> <Bildpfad> <Adresse> <Protokoll> <Fahrstufen> <Fahrtrichtung (True = vorwärts)> <Beschleunigungszeit in s> <Funktionsliste {name, sende_nr, wert, Joybutton} und erzeugt daraus Lokobjekte
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
		return loks	

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
			label = gtk.Label()
			label.show()
			label.set_markup("<b>" + begriff + "</b>")
			self.attach(label, 0, 1, i, (i+1))
			i = i + 1
		self.definitionen = [
		"Die Nummer, die über die Anzeigereihenfolge der Loks im Fahrprogramm entscheidet:\nKleine Zahl links, große Zahl rechts",
		"Der Name der Lok",
		"Das Digitalprotokoll, dass vom Lokdecoder verwendet wird:\n	-> M 1: Märklin Motorola 1. Version\n	-> M 2: Märklin Motorola 2. Version\n	-> NMRA: DCC Standard",
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
	def __init__(self, lok_treeview, funktions_treeview, loks, ladeziel):
		self.loks = loks
		self.lok_treeview = lok_treeview
		self.funktions_treeview = funktions_treeview
		self.ladeziel = ladeziel
		gtk.Button.__init__(self, "Laden")
		self.connect("clicked", self.laden)
		self.show()
		
	def laden(self, *args):
		try:
			verzeichnis = self.ladeziel.get_text()
			loks = pickle.load(open(verzeichnis))
			self.lok_treeview.laden(loks)
			self.funktions_treeview.laden(loks)
			print "Einstellungen wurden aus " + verzeichnis + " geladen."
		except:
			print "Einstellungen konnten nicht geladen werden, angegebene Datei ist nicht gültig."

class Speicherbutton(gtk.Button):
	def __init__(self, textfeld, grundbox):
		gtk.Button.__init__(self, "Speichern")
		self.grundbox = grundbox
		self.speicherziel = textfeld
		self.connect("clicked", self.speichern)
		self.show()
		
	def speichern(self, *args):
		verzeichnis = self.speicherziel.get_text()
		try:
			loks = self.grundbox.get_lokliste()
			if verzeichnis != "" and verzeichnis[len(verzeichnis)-4:len(verzeichnis)] != ".elc": # Wenn Dateiendung fehlt und ein Dateiname angegeben wurde, Endung anhängen
				verzeichnis += ".elc"
			pickle.dump(loks, open(verzeichnis, 'wb'))
			print "Einstellungen wurden gespeichert in " + verzeichnis
		except:
			print "Speichern fehlgeschlagen, angegebener Pfad ist nicht gültig."

class Speicherzielfeld(gtk.Entry):
	def __init__(self):
		gtk.Entry.__init__(self)
		self.show()
		
class Buttonbox_oben(gtk.HButtonBox):
	def __init__(self, grundbox, lokliste, function_mapping_box, loks):
		gtk.HButtonBox.__init__(self)
		self.set_layout(gtk.BUTTONBOX_START)
		self.legendebutton = Legendebutton()
		self.textfeld_speicherziel = Speicherzielfeld()
		self.speicherbutton = Speicherbutton(self.textfeld_speicherziel, grundbox)
		self.ladebutton = Ladebutton(lokliste, function_mapping_box, loks, self.textfeld_speicherziel)
		
		self.add(self.legendebutton)
		self.add(self.ladebutton)
		self.add(self.speicherbutton)
		self.add(self.textfeld_speicherziel)
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
		print nr
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

class HBoxMitte(gtk.HBox):
	def __init__(self, loks):
		gtk.HBox.__init__(self)
		self.function_mapping_box = FunctionMappingBox(loks)
		self.trennstrich = gtk.VSeparator()
		self.trennstrich.show()
		self.lokliste = Lokliste(loks, self.function_mapping_box)		
		self.pack_start(self.lokliste)
		self.pack_start(self.trennstrich)
		self.pack_start(self.function_mapping_box)
		self.show()
		
class HBoxUnten(gtk.HBox):
	def __init__(self, loktreeview, lokliste, sort_model, funktionsbox):
		gtk.HBox.__init__(self)
		self.buttonbox_links = Buttonbox_lokaktionen(loktreeview, lokliste, sort_model, funktionsbox)
		self.buttonbox_rechts = Buttonbox_funktionsaktionen(funktionsbox)
				
		self.pack_start(self.buttonbox_links)
		self.pack_start(self.buttonbox_rechts)
		self.show()

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
		self.combostore_protokoll.append(["NMRA"])
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
		self.append_column(gtk.TreeViewColumn("ID", self.textrenderer, text = 0))
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
			if funktion["SendeNr"] > self.anzahl_funktionen:
				self.anzahl_funktionen = funktion["SendeNr"]

	def an_server_senden(self, socket):
		self.letzte_gesendete_geschwindigkeit = int(self.geschwindigkeit)
		geschaltet = []
		for i in range(self.anzahl_funktionen):
			geschaltet.append(False)
		for funktion in self.funktionen:
			if funktion["Wert"]:
				geschaltet[funktion["SendeNr"]-1] = True
		funktionen = " ".join(str(int(n)) for n in geschaltet)
		sendetext = "SET 1 GL " + str(self.adresse) + " " + str(int(self.richtung)) + " " + str(int(self.geschwindigkeit)) + " " + str(self.fahrstufen) + " " + funktionen + "\n"
		print
		print sendetext
		socket.send(sendetext)
		print socket.recv(4096)
	
	def joystick_beschleunigung(self, wert, regler):
		self.geschwindigkeit = self.geschwindigkeit - wert * (0.2/3 * self.fahrstufen)
		if self.geschwindigkeit < 0:
			self.geschwindigkeit = 0
		if self.geschwindigkeit > self.fahrstufen:
			self.geschwindigkeit = self.fahrstufen
		regler[self.id].geschwindigkeitsregler.set_value(self.geschwindigkeit)

if __name__ == "__main__":	
	fenster = Fenster("ELECTRIP - Konfiguration")
	gtk.main()
