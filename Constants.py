#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ELECTRIP - Umgebungskonstanten

from gi.repository import GObject

# 0. ----------- Allgemein -----------

# 0.1. Version
ELECTRIP_VERSION = "2.1.3"

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

# 1.2.2 ServerTab
CONFIG_SERVER_TEXT_PARAMETERS= [
("Host", "Die IP-Adresse des Rechners auf dem der Server läuft"),
("Port", "Der Port unter dem der Server erreichbar ist, standardmäßig 4303"),
("Bus", "Der Bus auf dem der Server Befehle empfangen soll, standardmäßig 1")
] # Namen und Definition der Parameter für die Kommunikation mit dem SRCP-Server

CONFIG_SERVER_TEXT_PARAMETERS_SHORT= [
"Host",
"Port",
"Bus"
] # Namen der Parameter für die Kommunikation mit dem SRCP-Server

CONFIG_SERVER_CHECKBUTTON_DEFINITIONS = [
("Schalte den Strom beim Starten der Steuerung ein")
]

CONFIG_SERVER_CHECKBUTTON_PARAMETERS_SHORT = [
("Power")
]

# 1.2.3 JoystickTab
CONFIG_JOYSTICK_TEXT_PARAMETERS = [
("Nothalt (JoyButton)", "Der Button am Gamepad, über den die Gleisspannung ausgeschaltet werden kann"),
("Richtungswender (JoyButton)", "Der Button am Joystick, der einen Richtungswechsel der Lokomotive bewirkt"),
("Beschleunigung (JoyAchse)", "Die Achse am Gamepad, mit der die Geschwindigkeit der Lok geregelt wird"),
("Fokus (JoyButton)", "Der Button am Gamepad, der die zurzeit ausgewählte Lok in den im Fenster sichtbaren Bereich holt")
] # Liste mit verständlicheren Namen für die Parameter (wird in der GUI angezeigt)

CONFIG_JOYSTICK_TEXT_PARAMETERS_SHORT = [
"Notstop",
"Richtungswender",
"Achse",
"Fokus"
] # Namen der Parameter für die Bedienung mit einem Joystick

CONFIG_JOYSTICK_CHECKBUTTON_DEFINITIONS = [
"Die ausgewählte Lok immer fokussieren, wenn nur ein Gamepad angeschlossen ist",
"Die Nummer des zugehörigen Tasters am Gamepad auf den Funktions-Buttons anzeigen"
]

CONFIG_JOYSTICK_CHECKBUTTON_PARAMETERS_SHORT = [
"AutoFokus",
"ShowFunktionButtonNr"
]

# 1.2.4 FunktionTreeView
CONFIG_FUNCTION_TREEVIEW_COLUMN_TYPES = [GObject.TYPE_INT, GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING] # Datentypen in den Spalten des FunktionTreeView

CONFIG_LOCO_FUNCTION_STANDARD_VALUES = [0, "", 0, "An", 0, "Umschalter"] # Standardwerte für neu eingefügte Zeilen

CONFIG_FUNCTION_COLUMN_NAMES_TOOLTIPS_RENDERERS = [
("Position", "Die Position der Funktion im Steuerungsfenster\nvon oben nach unten", 1),
("Bezeichnung", "Der Name der Funktion ('Licht', 'Hupe' ...)", 0),
("Funktion", "Die Nummer der Funktion im Lokdecoder", 0),
("Wert", "Der voreingestellte Zustand der Funktion: An oder Aus", 2),
("JoyButton", "Der Button am JoyStick, dem die Lokfunktion zugewiesen ist", 0),
("Schaltart", "Die Art, mit der eine Funktion durch einen Joystick-Button geschaltet wird: Taster oder Umschalter", 3)
]

# 1.2.5 LokTreeView
CONFIG_LOCO_TREEVIEW_COLUMN_TYPES = [GObject.TYPE_INT, GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_DOUBLE, GObject.TYPE_STRING, GObject.TYPE_STRING] # Datentypen in den Spalten des LokTreeView

CONFIG_LOCO_STANDARD_VALUES = [0, "", 0, "M 1", 14, 3.0, "Vorwärts", ""] # Standardwerte für neu eingefügte Zeilen

CONFIG_LOCO_COLUMN_NAMES_TOOLTIPS_RENDERERS = [
("Position", "Die Position der Lok im Steuerungsfenster\nvon links nach rechts", 1),
("Lokomotive", "Der Name der Lokomotive, z.B. 'BR 218'", 0),
("Adresse", "Die Adresse des Digitaldecoders der Lok", 0),
("Protokoll", "Das Digitalprotokoll, das vom Lokdecoder verwendet wird:\n	-> M 1: Märklin Motorola 1. Version\n	-> M 2: Märklin Motorola 2. Version\n	-> N1: DCC kurzes Adressformat\n	-> N2: DCC langes Adressformat", 2),
("Fahrstufen", "Die Anzahl Fahrstufen, die der Lokdecoder besitzt", 3),
("Beschleunigungsdauer", "Die Zeit, die benötigt wird, um die Fahrstufe der Lok bei voller Auslenkung des Joysticks von 0 auf den höchstmöglichen Wert zu bringen", 0),
("Fahrtrichtung", "Die voreingestellte Fahrtrichtung der Lokomotive", 4),
("Bild", "Der Pfad an dem das passende Lokbild abgelegt ist", 1)
]

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
