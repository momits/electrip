#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from gi.repository import GdkPixbuf, GObject

import threading
import time
from math import pi
from os.path import normpath

from locked_print import locked_print
try:
    import pygame
    from pygame.locals import *
except ImportError:
    locked_print("PyGame ist nicht installiert, Gamepads "
                 "und die Geräuschsimulation können nicht "
                 "verwendet werden.")
    pygame_installed = False
else:
    pygame_installed = True

from constants import STOP_EVENT, END_EVENT_LOWER_BOUND
import config

 # class for mixed event handling: gamepads + sound
class EventHandlerThread(threading.Thread):
    running = False
    
    def __init__(self, config_copy):
        self.channels = []
        self.quit_callbacks = []
        self.callbacks = {}
        threading.Thread.__init__(self)
        global Config
        Config = config_copy
        pygame.mixer.pre_init(frequency=Config.sound.sampling_rate,
                              size=-16,
                              channels=2,
                              buffer=512)
        pygame.init()
        pygame.joystick.init()
        pygame.mixer.set_num_channels(255)
    
    def joystick_init(self, controllers, emergency_button):
        self.image_list = [GdkPixbuf.Pixbuf.new_from_file(normpath("icons/gamepads/" + 
                                                                   str(img_nr) + ".png"))
                           for img_nr in range(1, 13)]
        
        self.joysticks = []
        locked_print("Initialisiere Joysticks / Gamepads:")
        for joy_id in xrange(pygame.joystick.get_count()):
            if not len(self.joysticks) == len(controllers):
                # appends joystick-triples of the format:
                # [pygame.joystick.Joystick-instance, loco_id, start_scrolling]
                # where start_scrolling may have the values
                # 0 = No, 1 = scroll to right, -1 = scroll to left
                joystick = pygame.joystick.Joystick(joy_id)
                self.joysticks.append([joystick, joy_id, 0])
                
                locked_print("-------- " , joystick.get_id() , " --------")
                joystick.init()
                locked_print(joystick.get_name())
                locked_print("Anzahl Achsen:", joystick.get_numaxes())
                locked_print("Anzahl Knöpfe:", joystick.get_numbuttons())
                
                controllers[joy_id].gamepad_image.set_from_pixbuf(self.image_list[joy_id])
                controllers[joy_id].joystick = joystick
            else:
                locked_print("Joystick '" + pygame.joystick.Joystick(joy_id).get_name() + \
                             "' wurde ignoriert, da ", pygame.joystick.get_count(),
                             " Joysticks zuviel für ", len(controllers), " Loks sind.")
        
        self.emergency_button = emergency_button
        self.auto_focus = len(self.joysticks) == 1 and Config.joystick.use_auto_focus
        self.controllers = controllers
        self.speed_thread = SpeedThread(self.joysticks, self.controllers)
    
    def run(self):
        self.speed_thread.start()
        self.running = True
        while self.running:
            event = pygame.event.wait()
            if event.type >= END_EVENT_LOWER_BOUND:
                channel_id = event.type - END_EVENT_LOWER_BOUND
                if channel_id in self.callbacks:
                    func, args = self.callbacks[channel_id]
                    # safe calling from a separate thread:
                    GObject.idle_add(func, *args)
            
            elif event.type == JOYBUTTONDOWN:
                loco_id = self.joysticks[event.joy][1]
                configured = False
                for function_button in self.controllers[loco_id].function_box.buttons:
                    if hasattr(function_button, "function") \
                    and event.button == function_button.function.button:
                        if function_button.get_sensitive():
                            GObject.idle_add(function_button.clicked)
                        configured = True
                
                if event.button == Config.joystick.reverse_button:
                    GObject.idle_add(self.controllers[loco_id].reverser.clicked)
                
                elif event.button == Config.joystick.emergency_button:
                    GObject.idle_add(self.emergency_button.clicked)
                
                elif event.button == Config.joystick.focus_button:
                    GObject.idle_add(self.controllers[loco_id].set_focus)
                
                elif event.button == Config.joystick.sound_button \
                and self.controllers[loco_id].loco.engine != None:
                    sound_switch = self.controllers[loco_id].function_box.sound_switch
                    if sound_switch.get_sensitive():
                        GObject.idle_add(sound_switch.clicked)
                
                elif not configured:
                    locked_print("Nicht konfigurierter Button wurde gedrückt.")
            
            elif event.type == JOYBUTTONUP:
                loco_id = self.joysticks[event.joy][1]
                for function_button in self.controllers[loco_id].function_box.buttons:
                    if hasattr(function_button, "function") \
                    and event.button == function_button.function.button:
                        if hasattr(function_button.function, "toggle_mode") \
                        and (function_button.function.toggle_mode == config.ToggleMode.PUSH or \
                             function_button.function.toggle_mode == config.ToggleMode.PUSH_LIMITED):
                            GObject.idle_add(function_button.clicked)
              
            elif event.type == JOYHATMOTION:
                direction = event.value[0]
                if direction == 1 != self.joysticks[event.joy][2]:
                    # set scroll-direction to the right
                    self.joysticks[event.joy][2] = 1
                    # scroll one position to the right
                    self.scroll(1, event.joy)
                    # after 500 ms, check if auto-scrolling should be enabled
                    GObject.timeout_add(500, self.set_auto_scroll, 1, event.joy)
                elif direction == -1 != self.joysticks[event.joy][2]:
                    # set scroll-direction to the right
                    self.joysticks[event.joy][2] = -1
                    # scroll one position to the left
                    self.scroll(-1, event.joy)
                    # after 500 ms, check if auto-scrolling should be enabled
                    GObject.timeout_add(500, self.set_auto_scroll, -1, event.joy)
                # if joyhat is not pressed anymore but we are still scrolling
                elif direction == 0 != self.joysticks[event.joy][2]:
                    # set scroll-direction to 0 (no scrolling)
                    self.joysticks[event.joy][2] = 0
            
            elif event.type == STOP_EVENT:
                self.running = False
                locked_print("EventHandlerThread beendet.")
    
    def change_loco(self, loco_id, new_loco_id, joystick):
        GObject.idle_add(self.controllers[loco_id].gamepad_image.clear)
        self.controllers[loco_id].joystick = None
        GObject.idle_add(self.controllers[new_loco_id].gamepad_image.set_from_pixbuf,
                         self.image_list[joystick])
        self.controllers[new_loco_id].joystick = self.joysticks[joystick][0]
        # if auto-focus is active, make the controller focus itself in the window
        if self.auto_focus:
            GObject.idle_add(self.controllers[new_loco_id].set_focus)
        loco_id = new_loco_id
        self.joysticks[joystick][1] = loco_id
    
    def scroll(self, direction, joystick):
        loco_id = self.joysticks[joystick][1]
        if direction == self.joysticks[joystick][2]:
            # no possibility to change if loco is at the right end
            if direction == 1 and loco_id < len(self.controllers) - 1:
                new_loco_id = loco_id
                # find next free loco_id
                while new_loco_id < len(Config.locos) - 1 \
                and self.controllers[new_loco_id].joystick != None:
                    new_loco_id += 1
                # check if loco is free (in case all locos are occupied by joysticks)
                if self.controllers[new_loco_id].joystick == None:
                    self.change_loco(loco_id, new_loco_id, joystick)
            
            # no posiibility to change if loco is at the left end
            elif direction == -1 and loco_id > 0:
                new_loco_id = loco_id
                while new_loco_id > 0 and self.controllers[new_loco_id].joystick != None:
                    new_loco_id -= 1
                if self.controllers[new_loco_id].joystick == None:
                    self.change_loco(loco_id, new_loco_id, joystick)
            # return True to keep the Timeout alive
            return True
    
    def set_auto_scroll(self, direction, joystick):
        # if the joyhat is still pushed in the same direction
        if self.joysticks[joystick][2] == direction:
            GObject.timeout_add(60, self.scroll, direction, joystick)
        return False
      
    def add_callback(self, channel_id, callback_func, *args):
        self.callbacks[channel_id] = callback_func, args
    
    def add_quit_callback(self, callback_func):
        self.quit_callbacks.append(callback_func)
    
    def queue_sound(self, channel_id, sound):
        if sound != None: # sounds are None when not configured
            self.channels[channel_id].queue(sound)
    
    def double_queue_sound(self, channel_id, sound):
        if sound != None:
            self.channels[channel_id].queue(sound)
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
        for func in self.quit_callbacks:
            func()
        pygame.event.post(pygame.event.Event(STOP_EVENT))
        pygame.mixer.quit()
        # remove globals and reference cycles
        global Config
        del Config
        del self.channels
        del self.callbacks
        del self.quit_callbacks
        del self.image_list
        del self.emergency_button
        del self.controllers
        del self.speed_thread

def create_sound_controller(engine_type, *args):
    if engine_type == config.EngineType.DIESEL:
        return DieselSoundController(*args)
    elif engine_type == config.EngineType.STEAM:
        return SteamSoundController(*args)

class SoundController(GObject.GObject):
    # state of the whole sound-controller:
    # if False, playback on every channel has stopped
    engine_is_running = False
    old_speed = 0
    
    __gsignals__ = {
      "speed-changed": (GObject.SIGNAL_RUN_FIRST, None, (int, float,)),
      "engine-idle": (GObject.SIGNAL_RUN_FIRST, None, ()),
      "engine-stopped": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
    
    def __init__(self, handler_thread, loco_engine, volume):
        GObject.GObject.__init__(self)
        self.mixer = handler_thread
        self.volume = volume
        
        if loco_engine.event_sounds != None:
            for event_sound in loco_engine.event_sounds:
                event_sound.sound = self.convert_to_sound(event_sound.file_path)
                event_sound.channel_id = self.mixer.acquire_channel_id()
#                if event_sound.repeat:
                self.mixer.add_callback(event_sound.channel_id,
                                        self.queue_event_sound, event_sound)
        self.engine = loco_engine
#        self.empty_sound = pygame.mixer.Sound("")
    
    def stop_event_sounds(self):
        if self.engine.event_sounds != None:
            for event_sound in self.engine.event_sounds:
                self.mixer.channels[event_sound.channel_id].stop()
    
    def check_event_sounds(self):
        current_time = time.time()
        self.accel = (self.speed - self.old_speed) / (current_time - self.old_time)
#        locked_print("new accel", self.accel)
        for event_sound in self.engine.event_sounds:
            if self.check_event_sound(event_sound) \
            and not self.mixer.channels[event_sound.channel_id].get_busy():
                self.mixer.queue_sound(event_sound.channel_id, event_sound.sound)
        self.old_time = current_time
        self.old_speed = self.speed
    
    def check_event_sound(self, event_sound):
        if event_sound.state:
            fulfilled = True
            if event_sound.min_accel != None:
                if self.accel < event_sound.min_accel:
                    fulfilled = False
            if event_sound.max_accel != None:
                if self.accel > event_sound.max_accel:
                    fulfilled = False
            if event_sound.min_speed != None:
                if self.speed < event_sound.min_speed:
                    fulfilled = False
            if event_sound.max_speed != None:
                if self.speed > event_sound.max_speed:
                    fulfilled = False
            return fulfilled
        else:
            return False
    
    def queue_event_sound(self, event_sound):
        # if the conditions for playing the event sound are still met,
        # put it in queue again
        if self.check_event_sound(event_sound) and self.engine_is_running:
            self.mixer.queue_sound(event_sound.channel_id, event_sound.sound)
    
    def convert_to_sound(self, sound_file):
        try:
            sound = pygame.mixer.Sound(sound_file)
            sound.set_volume(self.volume)
            return sound
        except pygame.error:
            locked_print("Not a valid sound_file:", sound_file)

class DieselSoundController(SoundController):
    segment_attributes = ["load_sound", "idle_sound", "accel_sound", "decel_sound"]
    engine_attributes = ["quit_sound", "start_sound", "idle_sound"]
    scheduled_speed = -1
    actual_speed = -1
    next_sound_level = None
    on_load = False
    
    def __init__(self, handler_thread, loco_engine, volume):
        SoundController.__init__(self, handler_thread, loco_engine, volume)
        self.engine_channel_id = self.mixer.acquire_channel_id()
        self.mixer.add_callback(self.engine_channel_id, self.update_engine_queue)
        
        for segment in self.engine.sound_segments:
            for attrib in self.segment_attributes:
                if hasattr(segment, attrib):
                    setattr(segment, attrib, self.convert_to_sound(getattr(segment, attrib)))
        for attrib in self.engine_attributes:
            if hasattr(self.engine, attrib):
                setattr(self.engine, attrib, self.convert_to_sound(getattr(self.engine, attrib)))
    
    # new speed may be a float!
    def set_scheduled_speed(self, speed):
        self.speed = speed
        self.scheduled_speed = self.engine.sound_function.get_segment_nr_from_x(speed)
        # if nothings played on engine_channel at the moment
        if not self.mixer.channels[self.engine_channel_id].get_busy():
            self.update_engine_queue()
            self.update_engine_queue()
        self.check_event_sounds()
    
    def start_engine(self):
        self.actual_speed = self.scheduled_speed = -1
        channel = self.mixer.channels[self.engine_channel_id]
        if not self.engine_is_running and not channel.get_busy():
            self.engine_is_running = True
            self.mixer.queue_sound(self.engine_channel_id, self.engine.start_sound)
            self.mixer.queue_sound(self.engine_channel_id, self.engine.idle_sound)
            self.old_time = time.time()
        else:
            raise RuntimeError("Engine is already running!")
    
    # starts the engine, then plays the sound at a specific speed
    def start_engine_with_speed(self, speed):
        self.actual_speed = self.scheduled_speed = self.engine.sound_function.get_segment_nr_from_x(speed)
        self.old_time = time.time()
        self.engine_is_running = True
        self.on_load = True
        # Must be called two times, to fill the pygame-queue
        self.update_engine_queue()
        self.update_engine_queue()
    
    def quit_engine(self):
        if self.engine_is_running and self.actual_speed == -1:
            self.engine_is_running = False
            self.mixer.queue_sound(self.engine_channel_id, self.engine.quit_sound)
        else:
            raise RuntimeError("You didn't start the engine or it is still running at a speed > 0!")
    
    def pause_engine(self): # stops the engine-sound 
        self.mixer.channels[self.engine_channel_id].stop()
        self.stop_event_sounds()
        self.engine_is_running = False
    
    def get_sound_for_acceleration(self):
        return self.engine.sound_segments[self.actual_speed + 1].accel_sound
    
    def get_sound_for_deceleration(self):
        return self.engine.sound_segments[self.actual_speed].decel_sound
    
    def get_sound_for_same_speed(self):
        actual_segment = self.engine.sound_segments[self.actual_speed]
        if self.actual_speed == -1:
            return self.engine.idle_sound
        elif self.on_load:
            return actual_segment.load_sound
        else:
            return actual_segment.idle_sound
    
    def update_engine_queue(self):
        if self.next_sound_level != None:
            self.emit("speed-changed", *self.next_sound_level)
            self.next_sound_level = None
            
        old_speed = self.actual_speed
        emit_idle = False
        if self.engine_is_running:
            if self.actual_speed < self.scheduled_speed:
                sound = self.get_sound_for_acceleration()
                self.actual_speed += 1
                self.on_load = True
            
            elif self.actual_speed == self.scheduled_speed:
                if self.actual_speed == -1:
                    emit_idle = True
                sound = self.get_sound_for_same_speed()
            
            elif self.actual_speed > self.scheduled_speed:
                sound = self.get_sound_for_deceleration()
                self.actual_speed -= 1
                self.on_load = False
            
            # it IS possible (by design) that the playback stream gets broken,
            # if a sound-engine is not configured correctly
            if sound != None:
                self.mixer.queue_sound(self.engine_channel_id, sound)
                sound_length = sound.get_length() # * 1000
            else:
                sound_length = 0.0
                
            if old_speed != self.actual_speed:
                self.next_sound_level = [self.actual_speed, sound_length]
            elif emit_idle:
                self.emit("engine-idle")
        
        elif not self.mixer.channels[self.engine_channel_id].get_busy():
            self.emit("engine-stopped")

class SteamSoundController(SoundController):
    timeout_id = None
    stroke_nr = 0
    speed = 0
    
    def __init__(self, handler_thread, loco_engine, volume):
        SoundController.__init__(self, handler_thread, loco_engine, volume)
        loco_engine.idle_sound = self.convert_to_sound(loco_engine.idle_sound)
        loco_engine.cylinder_steam_sound = self.convert_to_sound(loco_engine.cylinder_steam_sound)
        self.steam_channel_id = self.mixer.acquire_channel_id()
        self.idle_channel_id = self.mixer.acquire_channel_id()
        self.stroke_channel_ids = [self.mixer.acquire_channel_id()
                                   for unused_stroke in xrange(loco_engine.nr_strokes)]
        
        for segment in self.engine.sound_segments:
            for nr, sound_path in enumerate(segment.stroke_sounds):
                segment.stroke_sounds[nr] = self.convert_to_sound(sound_path)
        
        self.mixer.add_callback(self.idle_channel_id, self.queue_idle_sound)
        self.mixer.add_quit_callback(self.quit)
        self.stroke_stop_event = threading.Event()
        self.stroke_stop_event.set()
    
    def start_engine(self):
        if not self.engine_is_running:
            self.engine_is_running = True
            self.mixer.double_queue_sound(self.idle_channel_id, self.engine.idle_sound)
            self.old_time = time.time()
            self.old_speed = 0
        else:
            raise RuntimeError("Engine is already running!")
    
    def quit_engine(self):
        self.pause_engine()
    
    def pause_engine(self):
        if hasattr(self, "stroke_stop_event"):
            self.stroke_stop_event.set()
        self.mixer.channels[self.idle_channel_id].stop()
        self.mixer.channels[self.steam_channel_id].stop()
        self.stop_event_sounds()
        self.engine_is_running = False
    
    def set_scheduled_speed(self, speed):
        self.speed = speed
        if speed > 0:
            self.pause_time = self.get_pause_time(speed)
        elif hasattr(self, "stroke_stop_event"):
            self.stroke_stop_event.set()
            if self.timeout_id != None:
                GObject.source_remove(self.timeout_id)
        self.check_event_sounds()
        self.check_start_thread()
    
    def check_start_thread(self):
        if self.stroke_stop_event.is_set() and self.speed > 0 \
        and self.engine_is_running:
            self.stroke_stop_event.clear()
            if not self.mixer.channels[self.steam_channel_id].get_busy():
                self.mixer.queue_sound(self.steam_channel_id,
                                       self.engine.cylinder_steam_sound)
                self.timeout_id = GObject.timeout_add(int(self.engine.stroke_start_delay * 1000),
                                                      self.start_stroke_thread)
            else:
                self.start_stroke_thread()
    
    # starts the engine, then plays the sound at a specific speed
    def start_engine_with_speed(self, speed):
        self.speed = speed
        self.start_engine()
        self.stroke_stop_event.clear()
        self.pause_time = self.get_pause_time(speed)
        self.start_stroke_thread()
    
    def get_pause_time(self, speed):
        return min((3.6 * self.engine.wheel_diameter * pi) / (speed * float(self.engine.nr_strokes)),
                   1.0 / self.engine.min_freq)
    
    def start_stroke_thread(self):
        self.stroke_thread = threading.Thread(target=self.play_next_stroke)
        self.stroke_thread.start()
        self.timeout_id = None
    
    def play_next_stroke(self):
        while not self.stroke_stop_event.is_set():
            start_time = time.time()
#            locked_print("Playing next stroke", self.stroke_nr, "after", start_time - old_time)
            stroke_sound = self.engine.sound_function.get_sound(self.speed,
                                                                "stroke_sounds")[self.stroke_nr]
            self.mixer.queue_sound(self.stroke_channel_ids[self.stroke_nr],
                                   stroke_sound)
            if self.stroke_nr < self.engine.nr_strokes - 1:
                self.stroke_nr += 1
            else:
                self.stroke_nr = 0
            needed_time = time.time() - start_time
            if needed_time < self.pause_time:
                self.stroke_stop_event.wait(self.pause_time - needed_time)
        self.check_start_thread()
    
    def queue_idle_sound(self):
        if self.engine_is_running:
            self.mixer.queue_sound(self.idle_channel_id, self.engine.idle_sound)
    
    def quit(self):
        self.engine_is_running = False
        self.stroke_stop_event.set()
        if self.timeout_id != None:
            GObject.source_remove(self.timeout_id)
        elif hasattr(self, "stroke_thread"):
            self.stroke_thread.join()

class FunctionSoundController:
    def __init__(self, handler_thread, function_sounds, volume):
        self.mixer = handler_thread
        for function_sound in function_sounds:
            if function_sound.file_path != None:
                function_sound.sound = pygame.mixer.Sound(function_sound.file_path)
                function_sound.sound.set_volume(volume)
            else:
                function_sound.sound = None
            function_sound.channel_id = self.mixer.acquire_channel_id()
            if function_sound.toggle_mode in [config.ToggleMode.SWITCH,
                                              config.ToggleMode.PUSH]:
                self.mixer.add_callback(function_sound.channel_id,
                                        self.queue_function_sound,
                                        function_sound)
    
    def queue_function_sound(self, function_sound):
        if function_sound.state:
            self.mixer.queue_sound(function_sound.channel_id,
                                   function_sound.sound)

class SpeedThread:
    def __init__(self, joysticks, controllers):
        self.joysticks = joysticks
        self.controllers = controllers
    
    def start(self):
        self.id = GObject.timeout_add(50, self.go)
    
    def quit(self):
        GObject.source_remove(self.id)
    
    def go(self):
        for joystick, loco_id, start_scrolling in self.joysticks:
            scale = self.controllers[loco_id].speed_scale
            if scale.get_sensitive():
                axis_value = joystick.get_axis(Config.joystick.accel_axis)
                if abs(axis_value) > Config.joystick.axis_threshold:
                    scale.set_value(Config.locos[loco_id].accelerate(axis_value))
        return True
