#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ELECTRIP - Umgebungskonstanten

from gi.repository import GObject

# 0. ----------- Allgemein -----------

# 0.1. Version
ELECTRIP_VERSION = "2.1.6"

# 0.2. ICONS
ICON_PATH_LIST = [
"Icons/logo_icon_128.png",
"Icons/logo_icon_64.png",
"Icons/logo_icon_32.png",
"Icons/logo_icon_16.png"
]

# ----------- 1. Konfiguration -----------

# 1.1. Speichern und Laden
CONFIG_LOCO_FUNCTION_PARAMETERS = ["Nr","Name","SendeNr","Wert","Button", "Taster"] # Namen der Parameter der Lok-Funktionen

# 1.2 GUI

# 1.2.1 LokFrame
CONFIG_PICTURE_COLUMN = 7 # Spalte im LokTreeView in der das Bild eingetragen wird

# 1.2.2 EntryTable
ENTRY_TABLE_INPUT_STRING = 0 # Eingabefeld
ENTRY_TABLE_INPUT_INT = 1 # Eingabefeld für Integer
ENTRY_TABLE_INPUT_FLOAT = 2 # Eingabefeld für Float
ENTRY_TABLE_INPUT_COMBO = 3 # ComboBox
ENTRY_TABLE_INPUT_EMPTY = 4 # Leeres Feld, kann mit speziellen Widgets gefüllt werden

# 1.2.3 ServerTab
CONFIG_SERVER_TEXT_PARAMETERS= [
("Host", "Die IP-Adresse des Rechners auf dem der Server läuft", "localhost", [ENTRY_TABLE_INPUT_STRING]),
("Port", "Der Port unter dem der Server erreichbar ist", 4303, [ENTRY_TABLE_INPUT_INT]),
("Bus", "Der Bus auf dem der Server Befehle empfangen soll", 1, [ENTRY_TABLE_INPUT_INT])
] # Namen und Definition der Parameter für die Kommunikation mit dem SRCP-Server

CONFIG_SERVER_TEXT_PARAMETERS_SHORT= [
"Host",
"Port",
"Bus"
] # Namen der Parameter für die Kommunikation mit dem SRCP-Server

CONFIG_SERVER_CHECKBUTTON_PARAMETERS = [
("Power", "Schalte den Strom beim Starten der Steuerung ein", True)
]

# 1.2.4 JoystickTab
CONFIG_JOYSTICK_TEXT_PARAMETERS = [
("Nothalt (JoyButton)", "Der Button am Gamepad, über den die Gleisspannung ausgeschaltet werden kann", None, [ENTRY_TABLE_INPUT_INT]),
("Richtungswender (JoyButton)", "Der Button am Joystick, der einen Richtungswechsel der Lokomotive bewirkt", None, [ENTRY_TABLE_INPUT_INT]),
("Beschleunigung (JoyAchse)", "Die Achse am Gamepad, mit der die Geschwindigkeit der Lok geregelt wird", None, [ENTRY_TABLE_INPUT_INT]),
("Fokus (JoyButton)", "Der Button am Gamepad, der die zurzeit ausgewählte Lok in den im Fenster sichtbaren Bereich holt", None, [ENTRY_TABLE_INPUT_INT])
] # Liste mit verständlicheren Namen für die Parameter (wird in der GUI angezeigt)

CONFIG_JOYSTICK_TEXT_PARAMETERS_SHORT = [
"Notstop",
"Richtungswender",
"Achse",
"Fokus"
] # Namen der Parameter für die Bedienung mit einem Joystick

CONFIG_JOYSTICK_CHECKBUTTON_PARAMETERS = [
("AutoFokus", "Die ausgewählte Lok immer fokussieren, wenn nur ein Gamepad angeschlossen ist", True),
("ShowFunktionButtonNr", "Die Nummer des zugehörigen Tasters am Gamepad auf den Funktions-Buttons anzeigen", False)
]


# 1.2.5 FunktionTreeView
CONFIG_FUNCTION_TREEVIEW_COLUMN_TYPES = [GObject.TYPE_INT, GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING] # Datentypen in den Spalten des FunktionTreeView

CONFIG_FUNCTION_TREEVIEW_STANDARD_VALUES = [0, "", 0, "An", 0, "Umschalter"] # Standardwerte für neu eingefügte Zeilen

CONFIG_FUNCTION_TREEVIEW_COLUMN_NAMES_TOOLTIPS_RENDERERS = [
("Position", "Die Position der Funktion im Steuerungsfenster\nvon oben nach unten", 1),
("Bezeichnung", "Der Name der Funktion ('Licht', 'Hupe' ...)", 0),
("Funktion", "Die Nummer der Funktion im Lokdecoder", 0),
("Wert", "Der voreingestellte Zustand der Funktion: An oder Aus", 2),
("JoyButton", "Der Button am Joystick, dem die Lokfunktion zugewiesen ist", 0),
("Schaltart", "Die Art, mit der eine Funktion durch einen Joystick-Button geschaltet wird: Taster oder Umschalter", 3)
]

# 1.2.6 LokSelectionTreeView
CONFIG_LOCO_SELECTION_TREEVIEW_COLUMN_TYPES = [GObject.TYPE_STRING]

CONFIG_LOCO_SELECTION_TREEVIEW_COLUMN_NAMES_TOOLTIPS_RENDERERS = [
("Zu konfigurierende Lok wählen", "", 0)
]

CONFIG_LOCO_PROPERTY_TREEVIEW_STANDARD_VALUES = ["Neue Lok"]

# 1.2.7 LokPropertyTable
CONFIG_LOCO_PROPERTY_TABLE_TEXT_PARAMETERS = [
("Adresse", "Die Adresse des Digitaldecoders der Lok", 0, [ENTRY_TABLE_INPUT_INT]),
("Protokoll", "Das Digitalprotokoll, das vom Lokdecoder verwendet wird:\n	-> M 1: Märklin Motorola 1. Version\n	-> M 2: Märklin Motorola 2. Version\n	-> N1: DCC kurzes Adressformat\n	-> N2: DCC langes Adressformat", None, [ENTRY_TABLE_INPUT_COMBO, GObject.TYPE_STRING, "M 1", "M 2", "N 1", "N 2"]),
("Fahrstufen", "Die Anzahl Fahrstufen, die der Lokdecoder besitzt", None, [ENTRY_TABLE_INPUT_COMBO, GObject.TYPE_INT, 14, 27, 28, 128]),
("Beschleunigungsdauer", "Die Zeit in s, die benötigt wird, um die Fahrstufe der Lok bei voller Auslenkung des Joysticks von 0 auf den höchstmöglichen Wert zu bringen", 3.75, [ENTRY_TABLE_INPUT_FLOAT]),
("Fahrtrichtung", "Die voreingestellte Fahrtrichtung der Lokomotive", None, [ENTRY_TABLE_INPUT_COMBO, GObject.TYPE_STRING, "Vorwärts", "Rückwärts"]),
("Bild", "Der Pfad an dem das passende Lokbild abgelegt ist", "", [ENTRY_TABLE_INPUT_EMPTY])
] # Namen und Definition der Parameter für die Eigenschaften einer Lok

# ----------- 2. Steuerung -----------

# 2.1. HBoxFunktionen
CONTROL_NUMBER_FUNCTION_BUTTONS = 5 # Anzahl der Funktionen-Buttons in einer Spalte, wenn mehr wird eine neue Spalte angelegt

# 2.2 Notstopbutton
CONTROL_EMERGENCY_COLOR_RED = [60000, 30000, 30000, 1.0] # RGBA-Farben für Notstopbutton

CONTROL_EMERGENCY_COLOR_GREY = [45600, 45600, 45600, 1.0]

CONTROL_EMERGENCY_COLOR_DARK_GREY = [20500, 20500, 20500, 1.0]

# ----------- 3. JoystickKonsole -----------
JOYSTICK_SCROLL_ACTIVATE_TIME = 500 # Zeit die der Joystick-Rundblickschalter gedrückt werden muss bis gescrollt wird (in ms)

JOYSTICK_SCROLL_REPEAT_TIME = 60 # Dauer eines Lokwechsels beim Scrollen (in ms)
