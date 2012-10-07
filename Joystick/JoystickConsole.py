#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from gi.repository import GdkPixbuf, GLib
from LockedPrint import locked_print
try:
    import pygame
    from pygame.locals import * # Importiere Konstanten (JOYBUTTTONDOWN, ...) für kurze Namen
except ImportError:
    locked_print("PyGame ist nicht installiert, Joysticks können nicht verwendet werden.")
import threading

class JoystickConsole():
    def __init__(self, config_copy, controller, emergency_button):
        global Config
        Config = config_copy
        pygame.init()
        
        pygame.joystick.init() # Joystick Modul initialisieren
        
        self.joysticks = []
        for id in xrange(pygame.joystick.get_count()):
            if not len(self.joysticks) == len(controller):
                self.joysticks.append([pygame.joystick.Joystick(id), id, 0]) # Liste mit Joystickobjekten erstellen Format: [joystick, zugehörige lok, start_scrolling (0 = Nein, 1 = Rechts, -1 = Links)] -> start_scrolling = True wenn joyhat 500 ms gedrückt wird
            else:
                locked_print("Joystick '" + pygame.joystick.Joystick(id).get_name() + "' wurde ignoriert, da ", pygame.joystick.get_count(), " Joysticks zuviel für ", len(controller), " Loks sind.")
        
        locked_print("Erkannte Joysticks:", len(self.joysticks))
        
        locked_print("\nJoystick - Initialisierung:")
        for joystick_lok in self.joysticks: # Daten der angeschlossenen Joysticks auslesen
            joystick = joystick_lok[0]
            locked_print("-------- " , joystick.get_id() , " --------")
            joystick.init() # Joystick initialisieren
            locked_print(joystick.get_name())
            locked_print("Anzahl Achsen:", joystick.get_numaxes())
            locked_print("Anzahl Knöpfe:", joystick.get_numbuttons(), "\n")
        
        self.joy_thread = JoystickThread(self.joysticks, controller, emergency_button)
        self.joy_thread.start()
        self.speed_thread = SpeedThread(self.joysticks, controller)
        self.speed_thread_id = GLib.timeout_add(50, self.speed_thread.go)
        
    
    def quit(self):
        locked_print("Stoppe Threads ...")
        self.joy_thread.quit()
        GLib.source_remove(self.speed_thread_id)
        pygame.event.post(pygame.event.Event(MOUSEBUTTONDOWN, {"pos": 0, "select_button": 0})) # Event posten, um joystick_thread zu beenden

class JoystickThread(threading.Thread):
    def __init__(self, joysticks, controller, emergency_button):
        super(JoystickThread, self).__init__()
        self.image_list = [GdkPixbuf.Pixbuf.new_from_file("Joystick/Pictures/" + str(bild_nr) + ".png") for bild_nr in range(1, 13)]
        self.emergency_button = emergency_button
        
        self.joysticks = joysticks
        if len(self.joysticks) == 1 and Config.joystick.use_auto_focus:
            self.auto_focus = True
        else:
            self.auto_focus = False
        locked_print("Auto-Fokus:", self.auto_focus)
        
        self.controller = controller
        
        for joystick_lok in self.joysticks:
            self.controller[joystick_lok[1]].loco_label.set_bold(True)
            self.controller[joystick_lok[1]].gamepad_image.set_from_pixbuf(self.image_list[joystick_lok[1]])
            self.controller[joystick_lok[1]].joystick = joystick_lok[0]
        self.running = True
    
    def run(self):
        while self.running:
            event = pygame.event.wait()
            if event.type == JOYBUTTONDOWN:
                loco_id = self.joysticks[event.joy][1]
                configured = False
                for nr, function in enumerate(Config.locos[loco_id].functions):
                    if event.button == function.button:
                        GLib.idle_add(self.controller[loco_id].function_box.buttons[nr].clicked)
                        configured = True
                if event.button == Config.joystick.reverse_button: # Gtk ist NICHT thread-safe, d.h. es können Probleme auftreten wenn von anderen threads Gtk-Objekte geändert werden
                    GLib.idle_add(self.controller[loco_id].reverser.clicked) # Deshalb: GLib.idle_add(Funktion, Parameter1, ...) -> Gtk-Hauptschleife führt Funktion mit Parametern aus, wenn sie Zeit hat
                elif event.button == Config.joystick.emergency_button:
                    GLib.idle_add(self.emergency_button.clicked)
                elif event.button == Config.joystick.focus_button:
                    GLib.idle_add(self.controller[loco_id].set_focus) # Lässt die Gtk-Hauptschleife die Funktion Regler.set_focus aufrufen, verhindert raise-conditions die zum crash führen können
                elif not configured:  # Ist Button nicht in Lokfunktionen oder Spezialbuttons, ist er nicht configured
                    locked_print("Nicht konfigurierter Button wurde gedrückt.")
                    
            elif event.type == JOYBUTTONUP:
                loco_id = self.joysticks[event.joy][1]
                for nr, function in enumerate(Config.locos[loco_id].functions):
                    if event.button == function.button and function.use_push_to_make:
                        GLib.idle_add(self.controller[loco_id].function_box.buttons[nr].clicked)
                        
            elif event.type == JOYHATMOTION:
                direction = event.value[0]
                if direction == 1 != self.joysticks[event.joy][2]:
                    self.joysticks[event.joy][2] = 1 # Starte scroll-Prozess nach rechts wenn joyhat länger als 500 ms gedrückt wird
                    self.scroll(1, event.joy)
                    GLib.timeout_add(500, self.set_auto_scroll, 1, event.joy)
                elif direction == -1 != self.joysticks[event.joy][2]:
                    self.joysticks[event.joy][2] = -1
                    self.scroll(-1, event.joy)
                    GLib.timeout_add(500, self.set_auto_scroll, -1, event.joy)
                elif direction == 0 != self.joysticks[event.joy][2]: # wenn joyhat losgelassen und noch gescrollt wird
                    self.joysticks[event.joy][2] = 0 # direction = 0 -> Scroll-Prozess wird gestoppt
                
        
    def change_loco(self, loco_id, new_loco_id, joystick):
        GLib.idle_add(self.controller[loco_id].gamepad_image.clear)
        GLib.idle_add(self.controller[loco_id].loco_label.set_bold, False)
        self.controller[loco_id].joystick = None
        GLib.idle_add(self.controller[new_loco_id].gamepad_image.set_from_pixbuf, self.image_list[joystick])
        GLib.idle_add(self.controller[new_loco_id].loco_label.set_bold, True)
        self.controller[new_loco_id].joystick = self.joysticks[joystick][0]
        if self.auto_focus: # Wenn nur ein Joystick, dann diesen fokussieren
            GLib.idle_add(self.controller[new_loco_id].set_focus) # Siehe oben
        loco_id = new_loco_id
        self.joysticks[joystick][1] = loco_id
        
    def scroll(self, direction, joystick):
        loco_id = self.joysticks[joystick][1]
        if direction == self.joysticks[joystick][2]:
            if direction == 1 and loco_id < len(self.controller) - 1: # wenn loco_id = länge von self.controller muss nicht gewechselt werden
                new_loco_id = loco_id
                while new_loco_id < len(Config.locos) - 1 and self.controller[new_loco_id].joystick != None:
                    new_loco_id += 1 # Findet nächste freie Lok-ID
                if self.controller[new_loco_id].joystick == None: # Prüfen, ob Lok frei ist (falls alle Loks mit Joysticks besetzt sind)
                    self.change_loco(loco_id, new_loco_id, joystick)
                
            elif direction == -1 and loco_id > 0: # wenn loco_id = 0 muss nicht gewechselt werden
                new_loco_id = loco_id
                while new_loco_id > 0 and self.controller[new_loco_id].joystick != None:
                    new_loco_id -= 1
                if self.controller[new_loco_id].joystick == None:
                    self.change_loco(loco_id, new_loco_id, joystick)
            return True # Wenn nichts zurückgegeben wird, wird der gobject-scroll-thread automatisch beendet

    
    def set_auto_scroll(self, richtung, joystick):
        if self.joysticks[joystick][2] == richtung: # wenn immer noch die gleiche joyhat-richtung gedrückt ist
            GLib.timeout_add(60, self.scroll, richtung, joystick)
        return False
    
    def quit(self):
        self.running = False

class SpeedThread():
    def __init__(self, joysticks, controllers):
        self.joysticks = joysticks
        self.controllers = controllers
        
    def go(self):
        for joystick, loco_id, start_scrolling in self.joysticks:
            self.controllers[loco_id].speed_scale.set_value(Config.locos[loco_id].accelerate(joystick.get_axis(Config.joystick.accel_axis)))
        return True
