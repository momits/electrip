#!/usr/bin/env python2.7
# -*- coding: UTF-8 -*-
import logging

from gi.repository import GdkPixbuf, GObject

from os.path import isfile
import threading
import time
from math import pi

from electrip.constants import STOP_EVENT, END_EVENT_LOWER_BOUND
from electrip import config

logger = logging.Logger(__name__)

try:
    import pygame
    from pygame.locals import *
except ImportError:
    logging.warning("PyGame ist nicht installiert, Gamepads "
                    "und die Geräuschsimulation können daher nicht "
                     "verwendet werden.")
    pygame_installed = False
else:
    pygame_installed = True


class Gamepad:
    """
    Representation of a Gamepad in the users hand, using
    a :class:`pygame.joystick.Joystick` internally.
    """
    def __init__(self, pygame_id):
        self.pygame_joystick = pygame.joystick.Joystick(pygame_id)
        self.pygame_joystick.init()
        self.pygame_id = pygame_id
        self.name = self.pygame_joystick.get_name()
        logger.info("--- GAMEPAD ---\n"
                    "Id: {:d}\n"
                    "Bezeichnung: {}\n"
                    "{:d} Achsen\n"
                    "{:d} Knöpfe\n"
                    .format(self.pygame_joystick.get_id(),
                            self.name,
                            self.pygame_joystick.get_numaxes(),
                            self.pygame_joystick.get_numbuttons()))
        self.scroll_direction = 0
        
    @staticmethod
    def gamepads(max_nr):
        """
        Generator which creates default :class:`Gamepad`-instances
        until all devices discovered by pygame are in use or *max_nr*
        is reached. Set *max_nr* to -1 if you dont need a limit.
        """
        for gamepad_id in range(pygame.joystick.get_count()):
            if gamepad_id == max_nr:
                logger.warning("Maximale Anzahl von Gamepads erreicht,"
                               "weitere Gamepads werden ignoriert.")
                break
            yield Gamepad(gamepad_id)


class EventHandlerThread(threading.Thread):
    """
    Class for pygame event handling. Deals with joystick input
    and sound output.
    """
    def __init__(self, sampling_rate):
        self.running = False
        self.channels = []
        self.quit_callbacks = []
        self.callbacks = {}
        threading.Thread.__init__(self)
        
        pygame.mixer.pre_init(frequency=sampling_rate,
                              size=-16,
                              channels=2,
                              buffer=512)
        pygame.init()
        pygame.joystick.init()
        pygame.mixer.set_num_channels(255)
    
    def gamepad_init(self,
                     button_pressed_cb,
                     button_released_cb,
                     horiz_joyhat_moved_cb,
                     axis_released_cb,
                     max_gamepads=-1):
        """
        This method must be called before :func:`EventHandlerThread.start` is called,
        as it prepares the :class:`EventHandlerThread` for gamepad-usage. The
        *..._cb*-arguments specify callback-methods for the following events:
            
            * *button_pressed_cb(gmp, button)*: *button* at gamepad
              *gmp* was pressed
            * *button_released_cb(gmp, button)*: *button* at gamepad
              *gmp* was released
            * *joyhat_moved_horiz_cb(gmp, direction)*: joyhat at gamepad
              *gmp* was moved to the left (``direction == -1``), the right
              (``direction == 1``) or released (``direction == 0``).
            * *axis_released_cb(gmp, axis)*: axis at gamepad
              *gmp* was released to center position.
        
        *max_gamepads* specifies the highest allowed number of
        :class:`Gamepad`-objects to be created by the :class:`EventHandlerThread`.
        
        Returns the number of gamepads which are in use after initialization. 
        """
        self.button_pressed_cb = button_pressed_cb
        self.button_released_cb = button_released_cb
        self.horiz_joyhat_moved_cb = horiz_joyhat_moved_cb
        self.axis_released_cb = axis_released_cb
        
        self.gamepads = [gmp for gmp in Gamepad.gamepads(max_gamepads)]
        
        return len(self.gamepads) 
    
    def run(self):
        self.running = True
        while self.running:
            event = pygame.event.wait()
            if event.type >= END_EVENT_LOWER_BOUND:
                channel_id = event.type - END_EVENT_LOWER_BOUND
                if channel_id in self.callbacks:
                    func, args = self.callbacks[channel_id]
                    GObject.idle_add(func, *args)
                    
            elif event.type == JOYAXISMOTION and event.value == 0:
                GObject.idle_add(self.axis_released_cb,
                                 self.gamepads[event.joy],
                                 event.axis)
            
            elif event.type == JOYBUTTONDOWN:
                GObject.idle_add(self.button_pressed_cb,
                                 self.gamepads[event.joy],
                                 event.button)
            
            elif event.type == JOYBUTTONUP:
                GObject.idle_add(self.button_released_cb,
                                 self.gamepads[event.joy],
                                 event.button)
              
            elif event.type == JOYHATMOTION:
                GObject.idle_add(self.horiz_joyhat_moved_cb,
                                 self.gamepads[event.joy],
                                 event.value[0])
            
            elif event.type == STOP_EVENT:
                self.running = False
                logger.info("EventHandlerThread beendet.")
      
    def add_callback(self, channel_id, callback_func, *args):
        """
        Adds *callback_func* to the list of functions which should
        be called when the channel with *channel_id* finished
        playing a sound. This is needed to implement gapless-playback
        of a stream of sounds, because pygame allows only one sound
        at a time to be queued for gapless playback on a channel.
        E.g.::
            
            # create a Sound-object to be played:
            tchoo = pygame.mixer.Sound("tchoo.ogg")
            
            # define a callback-function:
            def repeat_sound():
                handler_thread.queue(tchoo)
            
            # assuming handler_thread is an EventHandlerThread-instance:
            channel_id = handler_thread.acquire_channel_id()
            handler_thread.add_callback(channel_id, repeat_sound)
            handler_thread.double_queue_sound(tchoo)
            
            # 'repeat_sound' will now be called whenever a sound on
            # channel with channel_id finishes, allowing to put the next
            # sound in the queue for gapless playback 
        """
        self.callbacks[channel_id] = callback_func, args
    
    def add_quit_callback(self, callback_func):
        """
        Adds *callback_func* to the list of functions which should
        be called when :func:`quit` is called.
        """
        self.quit_callbacks.append(callback_func)
    
    def queue_sound(self, channel_id, sound):
        """
        Calls :func:`pygame.mixer.Channel.queue` on the channel belonging
        to *channel_id*, passing *sound* as parameter. *sound* is allowed to be
        ``None``, nothing will happen then.
        """
        if sound: # sounds are None when not configured
            self.channels[channel_id].queue(sound)
    
    def double_queue_sound(self, channel_id, sound):
        """
        Calls :func:`pygame.mixer.Channel.queue` on the channel with
        *channel_id* twice. Results in the channel playing *sound* and having
        *sound* in the queue, which is useful to start gapless playback.
        *sound* is allowed to be ``None``, nothing will happen then.
        """
        if sound:
            self.channels[channel_id].queue(sound)
            self.channels[channel_id].queue(sound)
            
    def play_sound(self, channel_id, sound, fade_in=0):
        """
        Starts playback of *sound* on the channel belonging
        to *channel_id*. If *fade_in* is set to a number of seconds,
        the sound is faded in accordingly.
        *sound* is allowed to be ``None``, nothing will happen then.
        """
        if sound:
            self.channels[channel_id].play(sound,
                                           fade_ms=int(1000 * fade_in))
            
    def stop_channel(self, channel_id, fade_out=0):
        """
        Stops playback on the channel belonging
        to *channel_id*. If *fade_out* is set to a number
        of seconds, the sound is faded out accordingly.
        """
        if fade_out:
            self.channels[channel_id].get_sound().fadeout(int(1000 * fade_out))
        else:
            self.channels[channel_id].stop()
    
    def acquire_channel_id(self):
        """
        Registers a new audio-channel, returning its id for usage
        with other methods of :class:`EventHandlerThread`.
        A maximum of 254 channels may be acquired (if exceeded an
        exception will be raised).
        """
        nr = len(self.channels)
        if nr < 255:
            channel = pygame.mixer.Channel(nr)
            channel.set_endevent(END_EVENT_LOWER_BOUND + nr)
            self.channels.append(channel)
        else:
            raise RuntimeError("Reached the limit of 255 allocated channels!")
        return nr
    
    def convert_to_sound(self, sound_file, volume):
        """
        Returns a newly created :class:`pygame.mixer.Sound`
        made of *sound_file* with volume *volume*.
        Returns ``None`` if *sound_file* is not a valid
        path to a sound-file.
        """
        # pygame creates empty sounds if the file path is wrong,
        # which is crazy behaviour we dont want
        if sound_file and isfile(sound_file):
            try:
                sound = pygame.mixer.Sound(sound_file)
                sound.set_volume(volume)
                return sound
            except pygame.error:
                pass
        logger.warning("Not a valid sound_file: {}".format(sound_file))
        return None
    
    def quit(self):
        """
        Stops the thread and calls the *quit_callbacks* which were registered
        using :func:`add_quit_callback`.
        """
        for func in self.quit_callbacks:
            func()
        pygame.event.post(pygame.event.Event(STOP_EVENT))
        pygame.mixer.quit()
        # remove reference cycles
        del self.channels
        del self.callbacks
        del self.quit_callbacks
        del self.button_pressed_cb
        del self.button_released_cb
        del self.horiz_joyhat_moved_cb 


def create_sound_controller(engine_type, *args):
    if engine_type == config.EngineType.DIESEL:
        return DieselSoundController(*args)
    elif engine_type == config.EngineType.STEAM:
        return SteamSoundController(*args)


class FunctionSoundPlayer:
    """
    Controls playback of all :class:`FunctionSound`-objects
    which belong to *loco*. Starts playing directly after
    instantiation.
    """
    def __init__(self, loco, handler_thread):
        self.loco = loco
        self.mixer = handler_thread
        
        for function_sound in loco.function_sounds:
            function_sound.sound = self.mixer.convert_to_sound(function_sound.file_path,
                                                               self.loco.sound_volume)
            function_sound.channel_id = self.mixer.acquire_channel_id()
            
            if function_sound.toggle_mode in [config.ToggleMode.PUSH,
                                              config.ToggleMode.SWITCH]:
                self.mixer.add_callback(function_sound.channel_id,
                                        self.check_queue_function_sound,
                                        function_sound)
            
            function_sound.watch("state", self.state_changed, function_sound)
    
    def check_queue_function_sound(self, function_sound):
        if function_sound.state:
            self.mixer.queue_sound(function_sound.channel_id,
                                   function_sound.sound)
            
    def state_changed(self, new_state, function_sound):
        if new_state:
            self.mixer.play_sound(function_sound.channel_id,
                                  function_sound.sound)
            if function_sound.toggle_mode in [config.ToggleMode.SWITCH,
                                              config.ToggleMode.PUSH]:
                # queue second time for gapless looping
                self.mixer.queue_sound(function_sound.channel_id,
                                       function_sound.sound)
        else:
            self.mixer.stop_channel(function_sound.channel_id)


class EventSoundPlayer:
    """
    Controls playback of all :class:`EventSound`-objects
    which belong to *loco*. Starts playing directly after
    instantiation.
    """
    def __init__(self, loco, handler_thread):
        self.checks = {}
        self.loco = loco
        self.mixer = handler_thread
        
        for event_sound in loco.event_sounds:
            event_sound.sound = self.mixer.convert_to_sound(event_sound.file_path,
                                                            self.loco.sound_volume)
            event_sound.channel_id = self.mixer.acquire_channel_id()
            self.mixer.add_callback(event_sound.channel_id,
                                    self.queue_event_sound,
                                    event_sound)
            
            # state
            checks = [self.check_state]
            event_sound.watch("state", self.attribute_changed, event_sound)
            
            # direction
            if event_sound.direction:
                checks.append(self.check_direction)
                loco.watch("direction", self.attribute_changed, event_sound)
            
            # speed
            if event_sound.min_speed or event_sound.max_speed:
                # no need to watch for speed if we watch the acceleration (s. below)
                if event_sound.min_speed:
                    checks.append(self.check_min_speed)
                
                if event_sound.max_speed:
                    checks.append(self.check_max_speed)
            
            # acceleration
            if event_sound.min_accel or event_sound.max_accel:
                loco.watch("acceleration", self.attribute_changed, event_sound)
                if event_sound.min_accel:
                    checks.append(self.check_min_accel)
                
                if event_sound.max_accel:
                    checks.append(self.check_max_accel)
            
            self.checks[event_sound] = checks
            # Check if we should start playback rightaway:
            self.check_all(event_sound)
        
    def queue_event_sound(self, event_sound):
        # if the conditions for playing the event sound are still met,
        # put it in queue again
        if self.check_all(event_sound):
            self.mixer.queue_sound(event_sound.channel_id, event_sound.sound)
        
    def check_state(self, event_sound):
        return event_sound.state
    
    def check_direction(self, event_sound):
        return event_sound.direction == self.loco.direction
    
    def check_min_accel(self, event_sound):
        return self.loco.acceleration >= event_sound.min_accel
    
    def check_max_accel(self, event_sound):
        return self.loco.acceleration <= event_sound.max_accel
    
    def check_min_speed(self, event_sound):
        return self.loco.speed >= event_sound.min_speed
    
    def check_max_speed(self, event_sound):
        return self.loco.speed <= event_sound.max_speed
    
    def attribute_changed(self, unused_new_value, event_sound):
        self.check_all(event_sound)
    
    def check_all(self, event_sound):
        """
        Checks if all conditions for the playback
        of *event_sound* are satisfied and starts playback
        if this is the case.
        """
        channel = self.mixer.channels[event_sound.channel_id]
        if all(check(event_sound) for check in self.checks[event_sound]):
            # don't interrupt if already playing
            if not channel.get_busy():
                self.mixer.play_sound(event_sound.channel_id,
                                      event_sound.sound,
                                      event_sound.fade_in)
        elif channel.get_busy() and not event_sound.play_to_end:
            self.mixer.stop_channel(event_sound.channel_id, event_sound.fade_out)


class SoundController(GObject.GObject):
    """
    Abstract base class for sound controllers using a :class:`Engine`-object
    *loco_engine* and the :class:`EventHandlerThread`-instance *handler_thread*
    for sound-playback.
    *volume* specifies the volume of the engine as a float from 0 to 1.
    :class:`SoundController` provides an interface for the playback of
    engine-sounds, according to the current speed
    of the loco.
    
    The :class:`SoundController` leaves most of the actual
    implementation to the child classes, to ensure high flexibility.
    
    Still, child classes must
    
        * use ``self.mixer`` (the reference to *handler_thread*) to control
          playback according to the current speed of the loco.
        * implement the *get_engine_is_running*-method 
        * implement the *do...*-methods
    
    E.g. an implementation to start a Diesel-engine in a subclass could be::
    
        class DieselSoundController(SoundController):
            # ...
            
            def do_start_engine(self):
                # queue the startup-sound and the idle-sound
                self.mixer.queue_sound(some_channel_id, self.engine.start_sound)
                self.mixer.queue_sound(some_channel_id, self.engine.idle_sound)
    """
    def __init__(self, handler_thread, loco_engine, volume):
        GObject.GObject.__init__(self)
        self.mixer = handler_thread
        self.volume = volume
        
        self.engine = loco_engine
        
        self.old_speed = 0
        
    def get_engine_is_running(self):
        """
        Returns whether the engine is running (sound is playing). To be
        implemented in a child class.
        """
        raise NotImplementedError()
    
    def start_engine(self):
        """
        Calls :func:`do_start_engine` if the engine is not running.
        Does nothing if the engine is running already.
        """
        if not self.get_engine_is_running():
            self.do_start_engine()
            self.old_time = time.time()
            self.old_speed = 0
            
    def do_start_engine(self):
        """
        Starts the engine and plays startup-sounds if the engine
        needs them.
        To be implemented in a child class.
        """
        raise NotImplementedError()
        
    
    def start_engine_at_speed(self, speed):
        """
        Calls :func:`do_start_engine_at_speed` if the engine is not
        running, otherwise does nothing.
        """
        if not self.get_engine_is_running():
            self.do_start_engine_at_speed(speed)
            self.old_time = time.time()
            self.old_speed = 0
            
    def do_start_engine_at_speed(self, speed):
        """
        Starts the engine without startup-sounds with the target
        speed *speed*.
        To be implemented in a child class.
        """
        raise NotImplementedError()
    
    def stop_engine(self):
        """
        Calls :func:`do_start_engine_at_speed` if the engine is running.
        """
        if self.get_engine_is_running():
            self.do_stop_engine()
    
    def do_stop_engine(self):
        """
        Stops the engine immediately.
        To be implemented in a child class.
        """
        raise NotImplementedError()
    
    def shutdown_engine(self):
        """
        If the engine is running, :func:`do_shutdown_engine` is called.
        Does nothing if the engine is not running.
        """
        if self.get_engine_is_running():
            self.do_shutdown_engine()
    
    def do_shutdown_engine(self):
        """
        Plays shutdown sound if the engine is not moving
        and makes sure there is no sound emission afterwards.
        To be implemented in a child class.
        """
        raise NotImplementedError()
    
    def set_target_speed(self, speed):
        """
        Sets the target speed for the engine to *speed*.
        Needs :func:`do_set_target_speed` to be implemented.
        """
        self.speed = speed
        self.do_set_target_speed(speed)
        
    def do_set_target_speed(self, speed):
        """
        Allows child classes to react to speed changes. They must
        try to move playback to the matching :class:`SoundSegment`
        as soon as possible.
        To be implemented in a child class.
        """
        raise NotImplementedError()


class DieselSoundController(SoundController):
    """
    A :class:`SoundController` for :class:`DieselEngine`-instances.
    Have a look at :class:`DieselEngine` and :class:`DieselSoundSegment`
    to understand how it works.
    
    The DieselSoundController emits three signals which can be used to
    synchronize the UI:
    
        * *sound-level-changed*: emitted when a new sound segment is
          reached and the transition begins
        * *engine-idle*: emitted when the diesel-engine runs idle and the loco
          is standing still (after the loco has been driving)
        * *engine-stopped*: emitted when the shutdown-process of the engine
          has completed
    """
    
    __gsignals__ = {
        "sound-level-changed": (GObject.SIGNAL_RUN_FIRST, None, (int, float,)),
        "engine-idle": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "engine-stopped": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
    
    def __init__(self, handler_thread, loco_engine, volume):
        SoundController.__init__(self, handler_thread, loco_engine, volume)
        self.engine_channel_id = self.mixer.acquire_channel_id()
        self.mixer.add_callback(self.engine_channel_id, self.update_engine_queue)
        
        for segment in self.engine.sound_segments:
            for attrib in ["load_sound", "idle_sound",
                           "accel_sound", "decel_sound"]:
                if hasattr(segment, attrib):
                    setattr(segment, attrib,
                            self.mixer.convert_to_sound(getattr(segment, attrib),
                                                        self.volume))
        for attrib in ["quit_sound", "start_sound", "idle_sound"]:
            if hasattr(self.engine, attrib):
                setattr(self.engine,
                        attrib,
                        self.mixer.convert_to_sound(getattr(self.engine, attrib),
                                                    self.volume))
        
        self.scheduled_segment_nr = -1
        self.actual_segment_nr = -1
        self.next_sound_level = None
        self.on_load = False
        self.shutdown = False
    
    def get_engine_is_running(self):
        return self.mixer.channels[self.engine_channel_id].get_busy()
    
    # new speed may be a float!
    def do_set_target_speed(self, speed):
        self.scheduled_segment_nr = self.engine.sound_function.get_segment_nr_from_x(speed)
        # if nothings played on engine_channel at the moment
        if not self.get_engine_is_running():
            self.update_engine_queue()
            self.update_engine_queue()
    
    def do_start_engine(self):
        self.shutdown = False
        self.actual_segment_nr = self.scheduled_segment_nr = -1
        self.mixer.queue_sound(self.engine_channel_id, self.engine.start_sound)
        self.mixer.queue_sound(self.engine_channel_id, self.engine.idle_sound)
    
    def do_start_engine_at_speed(self, speed):
        self.shutdown = False
        self.actual_segment_nr = self.scheduled_segment_nr = \
            self.engine.sound_function.get_segment_nr_from_x(speed)
        self.on_load = True
        # Must be called two times, to fill the pygame-queue
        self.update_engine_queue()
        self.update_engine_queue()
    
    def do_shutdown_engine(self):
        self.shutdown = True
        if self.actual_segment_nr == -1:
            self.mixer.queue_sound(self.engine_channel_id, self.engine.quit_sound)
    
    def do_stop_engine(self):
        self.shutdown = True
        self.mixer.stop_channel(self.engine_channel_id)
    
    def get_sound_for_acceleration(self):
        return self.engine.sound_segments[self.actual_segment_nr + 1].accel_sound
    
    def get_sound_for_deceleration(self):
        return self.engine.sound_segments[self.actual_segment_nr].decel_sound
    
    def get_sound_for_same_speed(self):
        actual_segment = self.engine.sound_segments[self.actual_segment_nr]
        if self.actual_segment_nr == -1:
            return self.engine.idle_sound
        elif self.on_load:
            return actual_segment.load_sound
        else:
            return actual_segment.idle_sound
    
    def update_engine_queue(self):
        if self.next_sound_level:
            self.emit("sound-level-changed", *self.next_sound_level)
            self.next_sound_level = None
            
        old_speed = self.actual_segment_nr
        emit_idle = False
        if not self.shutdown:
            if self.actual_segment_nr < self.scheduled_segment_nr:
                sound = self.get_sound_for_acceleration()
                self.actual_segment_nr += 1
                self.on_load = True
            
            elif self.actual_segment_nr == self.scheduled_segment_nr:
                if self.actual_segment_nr == -1:
                    emit_idle = True
                sound = self.get_sound_for_same_speed()
            
            elif self.actual_segment_nr > self.scheduled_segment_nr:
                sound = self.get_sound_for_deceleration()
                self.actual_segment_nr -= 1
                self.on_load = False
            
            # it IS possible that the playback stream gets broken,
            # if a sound-engine is not configured correctly
            if sound:
                self.mixer.queue_sound(self.engine_channel_id, sound)
                sound_length = sound.get_length()
            else:
                sound_length = 0.0
                
            if old_speed != self.actual_segment_nr:
                self.next_sound_level = [self.actual_segment_nr, sound_length]
            elif emit_idle:
                self.emit("engine-idle")
        
        elif not self.get_engine_is_running():
            self.emit("engine-stopped")


class SteamSoundController(SoundController):
    """
    A SoundController for :class:`SteamEngine`-instances.
    Have a look at :class:`SteamEngine` and :class:`SteamSoundSegment`
    to understand how it works.
    """
    def __init__(self, handler_thread, loco_engine, volume):
        SoundController.__init__(self, handler_thread, loco_engine, volume)
        loco_engine.idle_sound = self.mixer.convert_to_sound(loco_engine.idle_sound, self.volume)
        loco_engine.cylinder_steam_sound = self.mixer.convert_to_sound(loco_engine.cylinder_steam_sound,
                                                                       self.volume)
        self.steam_channel_id = self.mixer.acquire_channel_id()
        self.idle_channel_id = self.mixer.acquire_channel_id()
        self.stroke_channel_ids = [self.mixer.acquire_channel_id()
                                   for unused_stroke in range(loco_engine.nr_strokes)]
        
        for segment in self.engine.sound_segments:
            for nr, sound_path in enumerate(segment.stroke_sounds):
                segment.stroke_sounds[nr] = self.mixer.convert_to_sound(sound_path, self.volume)
        
        self.mixer.add_callback(self.idle_channel_id, self.queue_idle_sound)
        self.mixer.add_quit_callback(self.quit)
        self.stroke_stop_event = threading.Event()
        self.stroke_stop_event.set()
        
        self.timeout_id = None
        self.stroke_nr = 0
        self.speed = 0
        self.engine_is_running = False
        
    def get_engine_is_running(self):
        return self.engine_is_running
    
    def do_start_engine(self):
        self.engine_is_running = True
        self.mixer.double_queue_sound(self.idle_channel_id, self.engine.idle_sound)
    
    def do_shutdown_engine(self):
        self.stop_engine()
    
    def do_stop_engine(self):
        self.engine_is_running = False
        if hasattr(self, "stroke_stop_event"):
            self.stroke_stop_event.set()
        for stroke in range(self.engine.nr_strokes):
            self.mixer.stop_channel(self.stroke_channel_ids[stroke])
        self.mixer.stop_channel(self.idle_channel_id)
        self.mixer.stop_channel(self.steam_channel_id)
    
    def do_set_target_speed(self, speed):
        if speed > 0:
            self.pause_time = self.get_pause_time(speed)
        elif hasattr(self, "stroke_stop_event"):
            self.stroke_stop_event.set()
            if self.timeout_id:
                GObject.source_remove(self.timeout_id)
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
    
    def do_start_engine_at_speed(self, speed):
        self.do_start_engine()
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
            stroke_sound = self.engine.sound_function.get_sound(self.speed,
                                                                "stroke_sounds")[self.stroke_nr]
            self.mixer.play_sound(self.stroke_channel_ids[self.stroke_nr], stroke_sound)
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
        if self.timeout_id:
            GObject.source_remove(self.timeout_id)
        elif hasattr(self, "stroke_thread"):
            self.stroke_thread.join()


def prepare_function_sounds(handler_thread, function_sounds, volume):
    """
    Creates a :class:`pygame.mixer.Sound` for every ``function_sound`` in
    *function_sounds* and stores it in ``function_sound.sound``.
    Registers a unique channel for the sound using *handler_thread* and
    stores it in ``function_sound.channel_id``.
    Makes sure the sound will be played according to its respective
    :class:`ToggleMode`.
    """
    for function_sound in function_sounds:
        function_sound.sound = handler_thread.convert_to_sound(function_sound.file_path,
                                                               volume)
        function_sound.channel_id = handler_thread.acquire_channel_id()
        if function_sound.toggle_mode in [config.ToggleMode.SWITCH,
                                          config.ToggleMode.PUSH]:
            handler_thread.add_callback(function_sound.channel_id,
                                        queue_function_sound,
                                        handler_thread,
                                        function_sound)


def queue_function_sound(handler_thread, function_sound):
    """
    Queues the *function_sound* using *handler_thread* if
    ``function_sound.state == True``.
    *function_sound* must have been prepared using
    :func:`prepare_function_sounds`.
    Internal callback method.
    """
    if function_sound.state:
        handler_thread.queue_sound(function_sound.channel_id,
                                   function_sound.sound)
