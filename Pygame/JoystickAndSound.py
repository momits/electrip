#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from gi.repository import GdkPixbuf, GObject
from LockedPrint import locked_print
try:
    import pygame
    from pygame.locals import * # Importiere Konstanten (JOYBUTTTONDOWN, ...) für kurze Namen
except ImportError:
    locked_print("PyGame ist nicht installiert, Joysticks können nicht verwendet werden.")
import threading
import config
from copy import deepcopy # TODO: remove this import when no need to debug anymore
from Constants import STOP_EVENT, END_EVENT_LOWER_BOUND

class EventHandlerThread(threading.Thread): # class for mixed event handling: gamepads + sound
    running = False
    callbacks = {}
    channels = []
    
    def __init__(self, config_copy):
        threading.Thread.__init__(self)
        global Config
        Config = config_copy
        pygame.init()
        pygame.joystick.init() # Initialize joystick
        pygame.mixer.init() # Initialize mixer
            
    def joystick_init(self, controllers, emergency_button):
        self.joysticks = []
        for id in xrange(pygame.joystick.get_count()):
            if not len(self.joysticks) == len(controllers):
                self.joysticks.append([pygame.joystick.Joystick(id), id, 0]) # Liste mit Joystickobjekten erstellen Format: [joystick, zugehörige lok, start_scrolling (0 = Nein, 1 = Rechts, -1 = Links)] -> start_scrolling = True wenn joyhat 500 ms gedrückt wird
            else:
                locked_print("Joystick '" + pygame.joystick.Joystick(id).get_name() + "' wurde ignoriert, da ", pygame.joystick.get_count(), " Joysticks zuviel für ", len(controllers), " Loks sind.")
        
        locked_print("Erkannte Joysticks:", len(self.joysticks))
        
        locked_print("Joystick - Initialisierung:")
        for joystick_loco in self.joysticks: # Daten der angeschlossenen Joysticks auslesen
            joystick = joystick_loco[0]
            locked_print("-------- " , joystick.get_id() , " --------")
            joystick.init() # Joystick initialisieren
            locked_print(joystick.get_name())
            locked_print("Anzahl Achsen:", joystick.get_numaxes())
            locked_print("Anzahl Knöpfe:", joystick.get_numbuttons())
        
        self.image_list = [GdkPixbuf.Pixbuf.new_from_file("Pygame/Pictures/" + str(img_nr) + ".png") for img_nr in range(1, 13)]
        self.emergency_button = emergency_button
        
        if len(self.joysticks) == 1 and Config.joystick.use_auto_focus:
            self.auto_focus = True
        else:
            self.auto_focus = False
        locked_print("Auto-Fokus:", self.auto_focus)
        
        self.controllers = controllers
        
        for joystick in self.joysticks:
            nr = joystick[1]
            self.controllers[nr].loco_label.set_bold(True)
            self.controllers[nr].gamepad_image.set_from_pixbuf(self.image_list[nr])
            self.controllers[nr].joystick = joystick[0]
            
        self.speed_thread = SpeedThread(self.joysticks, self.controllers)

    def run(self):
        self.speed_thread.start()
        self.running = True
        while self.running:
            event = pygame.event.wait()
            if event.type >= END_EVENT_LOWER_BOUND:
                channel_id = event.type - END_EVENT_LOWER_BOUND
                if channel_id in self.callbacks:
                    self.callbacks[channel_id]()
                
            elif event.type == JOYBUTTONDOWN:
                loco_id = self.joysticks[event.joy][1]
                configured = False
                for nr, function in enumerate(Config.locos[loco_id].functions):
                    if event.button == function.button:
                        GObject.idle_add(self.controllers[loco_id].function_box.buttons[nr].clicked)
                        configured = True
                if event.button == Config.joystick.reverse_button: # Gtk ist NICHT thread-safe, d.h. es können Probleme auftreten wenn von anderen threads Gtk-Objekte geändert werden
                    GObject.idle_add(self.controllers[loco_id].reverser.clicked) # Deshalb: GObject.idle_add(Funktion, Parameter1, ...) -> Gtk-Hauptschleife führt Funktion mit Parametern aus, wenn sie Zeit hat
                elif event.button == Config.joystick.emergency_button:
                    GObject.idle_add(self.emergency_button.clicked)
                elif event.button == Config.joystick.focus_button:
                    GObject.idle_add(self.controllers[loco_id].set_focus) # Lässt die Gtk-Hauptschleife die Funktion Controller.set_focus aufrufen, verhindert raise-conditions die zum crash führen können
                elif not configured:  # Ist Button nicht in Lokfunktionen oder Spezialbuttons, ist er nicht configured
                    locked_print("Nicht konfigurierter Button wurde gedrückt.")
                    
            elif event.type == JOYBUTTONUP:
                loco_id = self.joysticks[event.joy][1]
                for nr, function in enumerate(Config.locos[loco_id].functions):
                    if event.button == function.button and function.use_push_to_make:
                        GObject.idle_add(self.controllers[loco_id].function_box.buttons[nr].clicked)
                        
            elif event.type == JOYHATMOTION:
                direction = event.value[0]
                if direction == 1 != self.joysticks[event.joy][2]:
                    self.joysticks[event.joy][2] = 1 # Starte scroll-Prozess nach rechts wenn joyhat länger als 500 ms gedrückt wird
                    self.scroll(1, event.joy)
                    GObject.timeout_add(500, self.set_auto_scroll, 1, event.joy)
                elif direction == -1 != self.joysticks[event.joy][2]:
                    self.joysticks[event.joy][2] = -1
                    self.scroll(-1, event.joy)
                    GObject.timeout_add(500, self.set_auto_scroll, -1, event.joy)
                elif direction == 0 != self.joysticks[event.joy][2]: # wenn joyhat losgelassen und noch gescrollt wird
                    self.joysticks[event.joy][2] = 0 # direction = 0 -> Scroll-Prozess wird gestoppt
                    
            elif event.type == STOP_EVENT:
                self.running = False
                locked_print("EventHandlerThread beendet.")
                
    def change_loco(self, loco_id, new_loco_id, joystick):
        GObject.idle_add(self.controllers[loco_id].gamepad_image.clear)
        GObject.idle_add(self.controllers[loco_id].loco_label.set_bold, False)
        self.controllers[loco_id].joystick = None
        GObject.idle_add(self.controllers[new_loco_id].gamepad_image.set_from_pixbuf, self.image_list[joystick])
        GObject.idle_add(self.controllers[new_loco_id].loco_label.set_bold, True)
        self.controllers[new_loco_id].joystick = self.joysticks[joystick][0]
        if self.auto_focus: # Wenn nur ein Joystick, dann diesen fokussieren
            GObject.idle_add(self.controllers[new_loco_id].set_focus) # Siehe oben
        loco_id = new_loco_id
        self.joysticks[joystick][1] = loco_id
        
    def scroll(self, direction, joystick):
        loco_id = self.joysticks[joystick][1]
        if direction == self.joysticks[joystick][2]:
            if direction == 1 and loco_id < len(self.controllers) - 1: # wenn loco_id = länge von self.controllers muss nicht gewechselt werden
                new_loco_id = loco_id
                while new_loco_id < len(Config.locos) - 1 and self.controllers[new_loco_id].joystick != None:
                    new_loco_id += 1 # Findet nächste freie Lok-ID
                if self.controllers[new_loco_id].joystick == None: # Prüfen, ob Lok frei ist (falls alle Loks mit Joysticks besetzt sind)
                    self.change_loco(loco_id, new_loco_id, joystick)
                
            elif direction == -1 and loco_id > 0: # wenn loco_id = 0 muss nicht gewechselt werden
                new_loco_id = loco_id
                while new_loco_id > 0 and self.controllers[new_loco_id].joystick != None:
                    new_loco_id -= 1
                if self.controllers[new_loco_id].joystick == None:
                    self.change_loco(loco_id, new_loco_id, joystick)
            return True # Wenn nichts zurückgegeben wird, wird der gobject-scroll-thread automatisch beendet

    def set_auto_scroll(self, direction, joystick):
        if self.joysticks[joystick][2] == direction: # wenn immer noch die gleiche joyhat-direction gedrückt ist
            GObject.timeout_add(60, self.scroll, direction, joystick)
        return False
                
    def add_callback(self, channel_id, callback_func):
        self.callbacks[channel_id] = callback_func
        
    def queue_sound(self, channel_id, sound):
        locked_print("\nqueueing", sound)
        self.channels[channel_id].queue(sound)
        
    def acquire_channel_id(self):
        nr = len(self.channels)
        if nr < 255:
            channel = pygame.mixer.Channel(nr)
            channel.set_endevent(END_EVENT_LOWER_BOUND + nr)
            self.channels.append(channel)
        return nr
        
    def quit(self):
        self.speed_thread.quit()
        pygame.event.post(pygame.event.Event(STOP_EVENT))
        pygame.mixer.quit()
            
class SoundController(GObject.GObject):
    engine_is_running = False
    scheduled_speed = 0
    actual_speed = 0
    on_load = False
    __gsignals__ = {
      "speed-changed": (GObject.SIGNAL_RUN_FIRST, None, (int, float,)),
      "engine-idle": (GObject.SIGNAL_RUN_FIRST, None, ()),
      "engine-stopped": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
    segment_attribs = ["load_sound", "idle_sound", "accel_sound", "decel_sound"]
    path_sound_segments = []
    
    def __init__(self, handler_thread, loco): # extras = [(channel_id1, extra_sound1), (channel_id2, extra_sound2) ...]
        GObject.GObject.__init__(self)
        self.mixer = handler_thread
        self.engine_channel_id = self.mixer.acquire_channel_id()
        self.mixer.add_callback(self.engine_channel_id, self.update_engine_queue)
        
        self.path_sound_segments = deepcopy(loco.sound_segments)
        for segment in loco.sound_segments:
            for attrib in self.segment_attribs:
                if hasattr(segment, attrib):
                    setattr(segment, attrib, self.convert_to_sound(getattr(segment, attrib)))
        self.sound_segments = loco.sound_segments
        
        self.start_engine_sound = self.convert_to_sound(loco.start_engine_sound)
        self.quit_engine_sound = self.convert_to_sound(loco.quit_engine_sound)
        #self.extras = loco.extras
        self.sound_function = config.SoundFunction(self.sound_segments)
        self.sound_speed_steps = len(self.sound_segments) + 1
    
    def convert_to_sound(self, sound_file):
        try:
            return pygame.mixer.Sound(sound_file)
        except pygame.error:
            locked_print("Not a valid sound_file:", sound_file)
    
    def start_engine(self):
        channel = self.mixer.channels[self.engine_channel_id]
        if not self.engine_is_running and not channel.get_busy():
            self.mixer.queue_sound(self.engine_channel_id, self.start_engine_sound)
            self.mixer.queue_sound(self.engine_channel_id, self.sound_segments[0].idle_sound)
            self.engine_is_running = True
            #self.set_speed(self.actual_speed)
        else:
            raise RuntimeError("Engine is already running!")
        
    def quit_engine(self):
        if self.engine_is_running and self.actual_speed == 0:
            self.mixer.queue_sound(self.engine_channel_id, self.quit_engine_sound)
            self.engine_is_running = False
        else:
            raise RuntimeError("You didn't start the engine or it is still running at a speed > 0!")
        
    def set_speed(self, speed): # new speed may be a float!
        #sound_speed = self.sound_function.get_segment_nr_from_x(speed)
        if self.engine_is_running:
            self.scheduled_speed = self.sound_function.get_segment_nr_from_x(speed) #min(self.sound_speed_steps, max(0, int(round(sound_speed))))
            locked_print("new scheduled speed", self.scheduled_speed)
        else:
            raise RuntimeError("You need to start the Engine first.")
            
    def extra_sound(self, nr):
        if self.extras == None:
            raise AttributeError("extras_sound_ids oder extras_channel_id wurden nicht konfiguriert.")
        else:
            self.mixer.queue_sound(*self.extras[nr])
            locked_print("Extra function added to queue_sound!")
            
    def update_engine_queue(self):
        old_speed = self.actual_speed
        emit_idle = False
        #locked_print("updating engine queue_sound")
        scheduled_segment = self.sound_segments[self.actual_speed]
        if self.engine_is_running:
            if self.actual_speed < self.scheduled_speed:
                print 1
                sound = scheduled_segment.accel_sound
                path = self.path_sound_segments[self.actual_speed].accel_sound #########
                self.actual_speed += 1
                self.on_load = True
                
            elif self.actual_speed == self.scheduled_speed:
                print 2
                if self.on_load:
                    sound = scheduled_segment.load_sound
                    path = self.path_sound_segments[self.actual_speed].load_sound ##########
                else:
                    if self.actual_speed == 0:
                        emit_idle = True
                    sound = scheduled_segment.idle_sound
                    path = self.path_sound_segments[self.actual_speed].idle_sound #############
                
            elif self.actual_speed > self.scheduled_speed:
                print 3
                sound = scheduled_segment.decel_sound
                path = self.path_sound_segments[self.actual_speed].decel_sound ##########
                self.actual_speed -= 1
                self.on_load = False
            
            if sound != None:
                locked_print("Going to play", path, "for speed", self.actual_speed, "with length", sound.get_length(), "s")
                self.mixer.queue_sound(self.engine_channel_id, sound)
            else:
                locked_print("Geräusch", self.actual_speed, "ist keine gültige Datei.")
            if old_speed != self.actual_speed:
                self.emit("speed-changed", self.actual_speed, sound.get_length() * 1000) # sound_length is needed in ms
            if emit_idle:
                self.emit("engine-idle")
                
        elif not self.mixer.channels[self.engine_channel_id].get_busy():
            self.emit("engine-stopped")

class SpeedThread():
    def __init__(self, joysticks, controllers):
        self.joysticks = joysticks
        self.controllers = controllers
        
    def start(self):
        self.id = GObject.timeout_add(50, self.go)
        
    def quit(self):
        GObject.source_remove(self.id)
        
    def go(self):
        for joystick, loco_id, start_scrolling in self.joysticks:
            self.controllers[loco_id].speed_scale.set_value(Config.locos[loco_id].accelerate(joystick.get_axis(Config.joystick.accel_axis)))
        return True
