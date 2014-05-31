#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository.GLib import GError
from gi.repository import GObject, Gtk, Pango, GdkPixbuf

import socket
import threading
import time

from electrip.concurrent import locked_print, SocketThread
from electrip import pygame_io
from electrip import config
from electrip.constants import CIRCLE_PATHS, SOUND_LEVEL_ANIM_RES
from electrip.utils import TwoWayDict

class MainBox(Gtk.Grid):
    """
    Root container for the control-ui.
    """
    def __init__(self, config, main_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        global Config
        Config = config.create_copy()
         
        self.socket_init()
         
        if not pygame_io.pygame_installed:
            dialog = Gtk.MessageDialog(main_window,
                                       0,
                                       Gtk.MessageType.WARNING,
                                       Gtk.ButtonsType.OK,
                                       "Die Bibliothek PyGame ist nicht "
                                       "installiert.\nGamepads und die "
                                       "Geräuschsimulation können daher "
                                       "nicht verwendet werden.")
            dialog.run()
            dialog.destroy()
        
        self.emergency_button = EmergencyButton(self.socket_thread)  
        self.scrolled_window = ScrolledWindow(self.socket_thread,
                                              self.emergency_button)
        self.add(self.scrolled_window)
        self.add(self.emergency_button)

        self.show_all()
    
    def quit(self):
        self.scrolled_window.controller_hub.quit()
        global Config
        del Config
        self.socket_thread.send_and_wait_for_answer("TERM 1 POWER\n")
        self.socket_thread.send_and_wait_for_answer("TERM 0 SESSION\n")
        self.socket_thread.quit()
        locked_print("Steuerung geschlossen.")
        self.destroy()
    
    def socket_init(self):
        """
        Creates a socket-connection as specified by ``JsonModel.server``,
        makes the handshake, initializes all locos and communicates
        their initial state to the server.
        """
        bus = str(Config.server.bus)
        handshake = ["SET CONNECTIONMODE SRCP COMMAND\n",
                     "GO\n",
                     "INIT " + bus + " POWER\n"]
        
        self.socket_thread = SocketThread(socket.create_connection((Config.server.host,
                                                                    Config.server.port)))
        self.socket_thread.start()
        
        # we will use blocking socket methods to ensure
        # correct sequential order of commands and avoid
        # overflow errors
        #-------- Handshake ----------
        locked_print("Socket-Verbindung ist aktiv:\n",
                     self.socket_thread.wait_for_answer())
        for msg in handshake:
            self.socket_thread.send_and_block_for_answer(msg)
        
        # ---------- Initialize Locos -------------
        for loco in Config.locos:
            # nr_functions_to_send is NOT the same as len(loco.functions),
            # but rather the highest decoder-function-nr
            if len(loco.functions) > 0:
                nr_functions_to_send = max(function.nr + 1
                                           for function in loco.functions)
            else:
                nr_functions_to_send = 0
            loco_srcp_init = "INIT " + bus + " GL " + str(loco.address) + " " + \
                   str(loco.protocol) + " " + str(int(loco.speed_steps)) + \
                   " " + str(nr_functions_to_send) + "\n"
            self.socket_thread.send_and_block_for_answer(loco_srcp_init)
            
            loco_srcp_status = loco.get_srcp_status(Config.server.bus)
            self.socket_thread.send_and_block_for_answer(loco_srcp_status)
        
class ScrolledWindow(Gtk.ScrolledWindow):
    def __init__(self, socket_thread, emergency_button):
        Gtk.ScrolledWindow.__init__(self)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.controller_hub = ControllerHub(socket_thread,
                                            emergency_button,
                                            self.get_hadjustment())
        self.add_with_viewport(self.controller_hub)
        
class ControllerHub(Gtk.Grid):
    """
    :class:`Gtk.Grid` which fills itself with :class:`LocoController`-
    instances. Responsible for creating a :class:`EventHandlerThread`
    and taking over gamepad-event-handling via
    :func:`EventHandlerThread.gamepad_init` if pygame is available.
    """
    def __init__(self, socket_thread, emergency_button, h_adjustment):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_column_spacing(8)
        self.set_margin_bottom(8)
        
        self.controllers = []
        self.emergency_button = emergency_button
        
        if pygame_io.pygame_installed:
            # pygame is available, thus gamepads may be used
            # 1. create event-thread and connect event handlers
            self.event_thread = pygame_io.EventHandlerThread(Config.sound.sampling_rate)
            if self.event_thread.gamepad_init(self.gamepad_button_pressed,
                                              self.gamepad_button_released,
                                              self.horiz_joyhat_moved,
                                              len(Config.locos)) > 0:
                # if the nr of gamepads we can use is > 0 we proceed:
                
                # 2. mapping allows us to track which loco belongs to which gamepad
                self.mapping = TwoWayDict()
                for loco_id, gmp in enumerate(self.event_thread.gamepads):
                    self.mapping[gmp] = loco_id
                
#                 # 3. set auto-focus according to the number of gamepads and the global setting
#                 # NOTE: the behaviour of this setting was recently changed to not
#                 # be restricted to one loco
#                 self.auto_focus = len(self.event_thread.gamepads) == 1 \
#                                   and Config.joystick.use_auto_focus
                
                self.accel_timeout_id = GObject.timeout_add(50, self.check_acceleration)
                
            self.event_thread.start()
        else:
            self.event_thread = None
        
        func_size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.VERTICAL)
        
        for i, loco in enumerate(Config.locos):
            self.controllers.append(LocoController(socket_thread,
                                                   loco,
                                                   h_adjustment,
                                                   func_size_group,
                                                   self.event_thread))
            self.add(self.controllers[i])
        
        if pygame_io.pygame_installed:
            for nr, gmp in enumerate(self.event_thread.gamepads):
                self.controllers[nr].gamepad_image.set_from_pixbuf(gmp.pixbuf)
    
    def gamepad_button_pressed(self, gamepad, button):
        """
        Checks if the pressed *button* is assigned an action
        at the :class:`LocoController` belonging to *gamepad*
        (e.g. switching a loco-function) or if it is assigned a
        global action (e.g. reverse loco direction, emergency stop ...)
        """
        loco_id = self.mapping[gamepad]
        configured = False
        for function_button in self.controllers[loco_id].function_box.buttons:
            if hasattr(function_button, "function") \
            and button == function_button.function.button:
                if function_button.get_sensitive():
                    function_button.clicked()
                configured = True
         
        if button == Config.joystick.reverse_button:
            self.controllers[loco_id].reverser.clicked()
         
        elif button == Config.joystick.emergency_button:
            self.emergency_button.clicked()
         
        elif button == Config.joystick.focus_button:
            self.controllers[loco_id].set_focus()
         
        elif button == Config.joystick.sound_button \
        and self.controllers[loco_id].loco.engine != None:
            sound_switch = self.controllers[loco_id].function_box.sound_switch
            if sound_switch.get_sensitive():
                sound_switch.clicked()
           
        elif not configured:
            locked_print("Nicht konfigurierter Button wurde gedrückt.")
    
    def gamepad_button_released(self, gamepad, button):
        """
        Checks if the toggle-mode of a function in a
        :class:`LocoController` identified by *gamepad* and *button*
        is of kind "PUSH" or "PUSH_LIMITED" (comp.
        :class:`config.loco_functions.ToggleMode`). If such function
        exists its state is switched.
        """
        loco_id = self.mapping[gamepad]
        for function_button in self.controllers[loco_id].function_box.buttons:
            if hasattr(function_button, "function") \
            and button == function_button.function.button:
                if hasattr(function_button.function, "toggle_mode") \
                and (function_button.function.toggle_mode == config.ToggleMode.PUSH or \
                     function_button.function.toggle_mode == config.ToggleMode.PUSH_LIMITED):
                    function_button.clicked()
    
    def horiz_joyhat_moved(self, gamepad, direction):
        """
        Makes *gamepad* scroll to the next loco in *direction*.
        """
#         old_direction = gamepad.scroll_direction
        gamepad.scroll_direction = direction
        
        if direction in (1, -1):# != old_direction:
            # scroll one position in 'direction'
            self.scroll(direction, gamepad)
            # after 500 ms, check if auto-scrolling should be enabled
            self.timeout_handle = GObject.timeout_add(500,
                                                      self.set_auto_scroll,
                                                      direction,
                                                      gamepad)
#         elif direction == -1:# != old_direction:
#             # scroll one position to the left
#             self.scroll(-1, gamepad)
#             # after 500 ms, check if auto-scrolling should be enabled
#             self.timeout_handle = GObject.timeout_add(500, self.set_auto_scroll, -1, gamepad)
            
        else:
            # remove auto-scrolling attempts
            GObject.source_remove(self.timeout_handle)
            
            
    def scroll(self, direction, gamepad):
        """
        Assigns the *gamepad* another loco to control, namely
        either the one at the controller at the right (``direction == True``)
        or the left side (``direction == False``) of the currently assigned loco.
        """
        loco_id = self.mapping[gamepad]
        # if direction != gamepad.scroll_direction the joyhat was already released
        if direction == gamepad.scroll_direction:
            # no possibility to change if loco is at the right end
            if direction == 1 and loco_id < len(self.controllers) - 1:
                new_loco_id = loco_id
                # find next free loco_id
                while new_loco_id < len(self.controllers) - 1 \
                and new_loco_id in self.mapping:
                    new_loco_id += 1
                # check if loco is free (in case all locos are occupied by gamepads)
                if not new_loco_id in self.mapping:
                    self.change_loco(loco_id, new_loco_id, gamepad)
            
            # no possibility to change if loco is at the left end
            elif direction == -1 and loco_id > 0:
                new_loco_id = loco_id
                while new_loco_id > 0 and new_loco_id in self.mapping:
                    new_loco_id -= 1
                if not new_loco_id in self.mapping:
                    self.change_loco(loco_id, new_loco_id, gamepad)
            
            # return true to keep the timeout alive
            return True
        
    def change_loco(self, loco_id, new_loco_id, gamepad):
        """
        Makes *gamepad* switch from controlling the Loco with *loco_id*
        to the Loco with *new_loco_id*. If auto-focus is active, makes
        the corresponding controller focus itself in the window.
        Attention: This is an internal method. No error handling is done here.
        Use :func:`scroll` instead.
        """
        self.controllers[loco_id].gamepad_image.clear()
        self.controllers[new_loco_id].gamepad_image.set_from_pixbuf(gamepad.pixbuf)
        
        # if auto-focus is active, make the controller focus itself in the window
        # using GObject.idle_add makes this work fluidly
        if Config.joystick.use_auto_focus:
            GObject.idle_add(self.controllers[new_loco_id].set_focus)
        
        self.mapping[gamepad] = new_loco_id
        
    def set_auto_scroll(self, direction, gamepad):
        """
        This method is called 500 ms after the joyhat has been pushed in
        *direction* (-1 or 1). If the joyhat is still pushed in the same direction,
        auto-scrolling in *direction* is activated, meaning :func:`scroll` will
        be called every 60 ms until the joyhat is released.
        """
        # if the joyhat is still pushed in the same direction
        if gamepad.scroll_direction == direction:
            GObject.timeout_add(60, self.scroll, direction, gamepad)
        return False
    
    def check_acceleration(self):
        """
        Iterates over all initialized :class:`Gamepad`-objects and
        sets the acceleration of the corresponding :class:`Loco`
        according to the deviation of the acceleration-axis of the
        gamepad.
        """
        for gamepad in self.event_thread.gamepads:
            scale = self.controllers[self.mapping[gamepad]].speed_scale
            if scale.get_sensitive():
                axis_value = -1 * gamepad.pygame_joystick.get_axis(Config.joystick.accel_axis)
                if abs(axis_value) > Config.joystick.axis_threshold:
                    scale.set_value(Config.locos[self.mapping[gamepad]].accelerate(axis_value))
        return True
                    
    def quit(self):
        if hasattr(self, "accel_timeout_id"):
            GObject.source_remove(self.accel_timeout_id)
        if self.event_thread:
            self.event_thread.quit()

class LocoController(Gtk.Grid):
    """
    Widget allowing to control a *loco*, using a speed-scale,
    a reverser-button and function-buttons.
    Also shows a loco-image as well as an image visualizing
    the gamepad which is currently controlling the loco.
    """
    def __init__(self,
                 socket_thread,
                 loco,
                 h_adjustment,
                 func_size_group,
                 event_thread=None):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(True)
        self.loco = loco
        self.loco_image = LocoImage(loco.img_path)
        
        if loco.engine != None and event_thread != None:
            loco.sound_controller = pygame_io.create_sound_controller(loco.engine.type,
                                                                      event_thread,
                                                                      loco.engine,
                                                                      loco.sound_volume)
            engine_type = loco.engine.type
        else:
            loco.sound_controller = None
            engine_type = None
        
        self.speed_scale = create_speed_scale(engine_type,
                                              loco,
                                              socket_thread,
                                              loco.sound_controller)
        self.loco_label = LocoLabel(loco)
        self.reverser = Reverser(loco, socket_thread, self.speed_scale)
        self.gamepad_image = Gtk.Image()
        # TODO: find alternative! (5px bigger than image, some themes
        # (e.g. Elementary) need this)
        self.gamepad_image.set_size_request(100, 76)
        self.h_adjustment = h_adjustment
        
        circle_pixbufs = dict([(name, GdkPixbuf.Pixbuf.new_from_file(path))
                               for name, path in CIRCLE_PATHS.items()])
        self.function_box = FunctionBox(self.loco,
                                        self.speed_scale,
                                        event_thread,
                                        socket_thread,
                                        circle_pixbufs)
        func_size_group.add_widget(self.function_box)
        
        self.add(self.loco_image)
        self.add(self.speed_scale)
        self.add(Gtk.Label.new("km/h"))
        self.add(self.loco_label)
        self.add(self.gamepad_image)
        self.add(self.reverser)
        self.add(self.function_box)
    
    # Put the LocoController in the visible area of ScrolledWindow
    def set_focus(self):
        allocation = self.get_allocation()
        self.h_adjustment.clamp_page(allocation.x,
                                     allocation.x + allocation.width)
    
class LocoImage(Gtk.Image):
    """
    Image using *path* as file-path, scaling down
    to 110x85 pixels automatically.
    """
    def __init__(self, path):
        Gtk.Image.__init__(self)
        self.set_size_request(110, 85)
        if path == None:
            self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
        else:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
                small_pixbuf = pixbuf.scale_simple(110,
                                                   85,
                                                   GdkPixbuf.InterpType.BILINEAR)
                self.set_from_pixbuf(small_pixbuf)
            except GError:
                self.set_from_stock(Gtk.STOCK_MISSING_IMAGE,
                                    Gtk.IconSize.BUTTON)
                locked_print("Dateipfad '" + path + "' für Lokbild ist ungültig.")

def create_speed_scale(engine_type, *args):
    if engine_type == None:
        return SpeedScale(*args)
    elif engine_type == config.EngineType.DIESEL:
        return DieselSpeedScale(*args)
    elif engine_type == config.EngineType.STEAM:
        return SteamSpeedScale(*args)

class SpeedScale(Gtk.Scale):
    """
    A :class:`Gtk.Scale` for controlling the speed of a loco.
    """
    def __init__(self, loco, socket_thread, sound_controller=None):
        Gtk.Scale.__init__(self)
        self.loco = loco
        self.socket_thread = socket_thread
        self.set_restrict_to_fill_level(False)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.set_adjustment(Gtk.Adjustment(0, 0, loco.max_speed,
                                           loco.max_speed / 50.0,
                                           loco.max_speed / 20.0, 0))
        self.connect("value-changed",
                     self.speed_changed,
                     sound_controller)
        self.set_inverted(True)
        self.set_digits(1)
        self.set_value_pos(Gtk.PositionType.BOTTOM)
        
    def send_srcp(self):
        """
        Send the current state of the loco to the server.
        """
        self.socket_thread.send_and_wait_for_answer(self.loco.get_srcp_status(Config.server.bus))
#         locked_print("Lok", self.loco.name, "fährt jetzt",
#                      self.loco.speed, "km/h, das entspricht",
#                      int(self.loco.speed_step), "Fahrstufen.")
        
    def speed_changed(self, scale, sound_controller):
        """
        Called when the user changed the speed (either by mouse, keys
        or gamepad).
        This default implementation just uses ``loco.speed_to_step_func``
        to estimate the speed-step to be sent.
        *sound_controller* is not used. May be overridden in child classes.
        """
        self.loco.speed = self.get_value()
        self.loco.speed_step = self.loco.speed_to_step_func.get_y(self.loco.speed)
        if int(self.loco.speed_step) != self.loco.last_speed_step:
            self.send_srcp()

class DieselSpeedScale(SpeedScale):
    """
    :class:`SpeedScale`-implementation for locos with a
    :class:`DieselEngine`. Visualizes the current "sound-position"
    using the 'fill-level'-property of :class:`Gtk.Scale` and
    :class:`Animator`.
    """
    
    __gsignals__ = {
      "started-driving": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
    
    def __init__(self, loco, socket_thread, sound_controller=None):
        SpeedScale.__init__(self, loco, socket_thread, sound_controller)
        sound_controller.connect("sound-level-changed", self.animate_fill_level)
        if Config.sound.show_level_bar:
            self.set_show_fill_level(True)
            self.set_fill_level(0)
        self.step = self.loco.max_speed / SOUND_LEVEL_ANIM_RES
        
        self.stop_handler_id = self.start_handler_id = None
        self.ignore_sound_changes = False
    
    def speed_changed(self, scale, sound_controller):
        self.loco.speed = self.get_value()
        self.loco.speed_step = self.loco.speed_to_step_func.get_y(self.loco.speed)
        real_speed_step = int(self.loco.speed_step)
        
        # if speed has changed
        if real_speed_step != self.loco.last_speed_step:
            if sound_controller.get_engine_is_running():
                if real_speed_step == 0 \
                and self.stop_handler_id == None:
                    self.stop_handler_id = sound_controller.connect("engine-idle",
                                                                    self.stop_loco)
                elif self.loco.last_speed_step == 0 \
                and self.start_handler_id == None:
                    self.start_handler_id = self.connect("started-driving",
                                                         self.start_loco)
            if self.start_handler_id == self.stop_handler_id == None:
                self.send_srcp()
        if sound_controller.get_engine_is_running():
            sound_controller.set_target_speed(self.loco.speed)
    
    # synchronize loco-speed with sound (loco does stop/start when sound is ready)
    def stop_loco(self, sound_controller):
        if int(self.loco.speed_step) == 0:
#            locked_print("--------- Stopping loco together with sound!! ---------")
            self.send_srcp()
        sound_controller.disconnect(self.stop_handler_id)
        self.stop_handler_id = None
        
    def start_loco(self, diesel_speed_scale):
        if int(self.loco.speed_step) != 0:
#            locked_print("--------- Starting loco together with sound!! ---------")
            self.send_srcp()
        self.disconnect(self.start_handler_id)
        self.start_handler_id = None
    
    def animate_fill_level(self, animator, sound_level, sound_length, last_time=None):
        if not self.ignore_sound_changes:
            if last_time == None:
#                locked_print("Sound of diesel-loco changed to nr",sound_level, "with length", sound_length)
                if sound_level == 0 and self.loco.last_speed_step == 0:
                    self.emit("started-driving")
            else:
#                locked_print("signal received: old animator has finished")
                # speed up animation to make it finish in the real left time
                sound_length -= time.time() - last_time
            if Config.sound.show_level_bar:
                # if animator lags behind played sound
                if hasattr(self, "animator") and not self.animator.stop_event.is_set():
                    # transmit time to allow speed up in next cycle
                    self.animator.connect("animation-finished",
                                          self.animate_fill_level,
                                          sound_level,
                                          sound_length,
                                          time.time())
                else:
                    if sound_level == -1:
    #                    locked_print("animating to 0")
                        self.animate_with_args(0, sound_length)
                    else:
    #                    locked_print("animating to", self.loco.engine.sound_function.segments[sound_level].end)
                        self.animate_with_args(self.loco.engine.sound_function.segments[sound_level].end,
                                               sound_length)
            
    def animate_with_args(self, sound_level, sound_length):
        start_val = self.get_fill_level()
        end_val = sound_level
        if start_val != end_val:
            self.animator = Animator(self.set_fill_level,
                                     start_val,
                                     end_val,
                                     self.step,
                                     sound_length)
            self.animator.start()

class SteamSpeedScale(SpeedScale):
    """
    :class:`SpeedScale`-implementation for locos with a
    :class:`SteamEngine`. Visualizes the current "sound-position"
    using the 'fill-level'-property of :class:`Gtk.Scale`.
    """
    def __init__(self, loco, socket_thread, sound_controller=None):
        SpeedScale.__init__(self, loco, socket_thread, sound_controller)
        if Config.sound.show_level_bar:
            self.set_show_fill_level(True)
            self.set_fill_level(0)
    
    def speed_changed(self, scale, sound_controller):
        self.loco.speed = self.get_value()
        self.loco.speed_step = self.loco.speed_to_step_func.get_y(self.loco.speed)
        if int(self.loco.speed_step) != self.loco.last_speed_step:
            self.send_srcp()
        if sound_controller.get_engine_is_running():
            sound_controller.set_target_speed(self.loco.speed)
            self.set_fill_level(self.loco.speed)
        
class Animator(GObject.GObject, threading.Thread):
    """
    Calls *method* at a regular interval, linearly
    increasing the parameter from *start_val* to *end_val*.
    *duration* specifies the duration of the animation,
    *step* specifies the resolution of the animation as
    the amount of increase per interval.
    When *end_val* is reached, the signal 'animation-finished'
    is emitted.
    """
    __gsignals__ = {
      "animation-finished": (GObject.SIGNAL_RUN_LAST, None, ()),
    }
    animating = False
    
    def __init__(self, method, start_val, end_val, step, duration):
        GObject.GObject.__init__(self)
        threading.Thread.__init__(self)
        self.method = method
        self.start_val = start_val
        self.val = self.start_val
        self.end_val = end_val
        self.step = step
        if self.start_val == self.end_val:
            raise ValueError("Fehler bei Animation: Start- und End-Werte identisch.")
        else:
            # calculate sleep time for the animation
            self.sleep_time = duration / (abs(start_val - end_val) / step)
        self.stop_event = threading.Event()
 
    def run(self):
        self.stop_event.clear()
        self.animating = True
        while not self.stop_event.is_set():
            start_time = time.time()
            if self.start_val < self.end_val:
                if self.val < self.end_val:
                    self.val = min(self.val + self.step, self.end_val)
                else:
                    self.stop_event.set()
            elif self.start_val > self.end_val:
                if self.val > self.end_val:
                    self.val = max(self.val - self.step, self.end_val)
                else:
                    self.stop_event.set()
            GObject.idle_add(self.method, self.val)
            time_left = start_time - time.time() + self.sleep_time
            if time_left > 0:
                self.stop_event.wait(time_left)
        self.animating = False
        del self.method
        GObject.idle_add(self.emit, "animation-finished")

class LocoLabel(Gtk.Label):
    """
    Label whose style-properties are adjusted so it looks
    good in a :class:`LocoController`
    """
    def __init__(self, loco):
        self.text = loco.name
        Gtk.Label.__init__(self, self.text)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_max_width_chars(20)
        self.set_margin_top(7)

class Reverser(Gtk.Button):
    """
    Button which toggles the direction of the loco.
    """
    def __init__(self, loco, socket_thread, scale):
        Gtk.Button.__init__(self)
        self.arrow_up = Gtk.Image.new_from_stock(Gtk.STOCK_GO_UP,
                                                 Gtk.IconSize.BUTTON)
        self.arrow_down = Gtk.Image.new_from_stock(Gtk.STOCK_GO_DOWN,
                                                   Gtk.IconSize.BUTTON)
        self.loco = loco
        self.set_arrow()
        self.connect("clicked", self.toggle_direction, socket_thread, scale)
        self.set_hexpand(True)

    def toggle_direction(self, button, socket_thread, scale):
        self.loco.toggle_direction()
        # if direction has changed but speed is already 0
        if int(self.loco.speed_step) == 0:
            socket_thread.send_and_wait_for_answer(self.loco.get_srcp_status(Config.server.bus))
        scale.set_value(0)
        self.set_arrow()
#         locked_print("\nLok",
#                      self.loco.name,
#                      "hat die Richtung gewechselt und fährt nun",
#                      self.loco.direction)
    
    def set_arrow(self):
        if self.loco.direction:
            self.set_image(self.arrow_up)
        else:
            self.set_image(self.arrow_down)

def create_engine_switch(engine_type, *args):
    if engine_type == config.EngineType.STEAM:
        return SteamEngineSwitch(*args)
    elif engine_type == config.EngineType.DIESEL:
        return DieselEngineSwitch(*args)

class EngineSwitch(Gtk.ToggleButton):
    """
    A :class:`Gtk.ToggleButton` toggling the start- and
    stop-process of *sound_controller*, using *speed_scale*
    to check whether the loco is driving or not.
    *circle_pixbuf* is the :class:`GdkPixbuf.Pixbuf` used
    as background for the :class:`CircleNumber` showing the
    corresponding gamepad-button.
    Creates *self.label* (using *circle_pixbuf* if
    ``JsonModel.joystick.show_function_nr == True``) without showing it.
    Child classes decide how *self.label* is displayed.
    """
    def __init__(self, sound_controller, speed_scale, circle_pixbuf):
        Gtk.ToggleButton.__init__(self)
        name_label = Gtk.Label("Fahrgeräusch")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        if Config.joystick.show_function_nr \
        and Config.joystick.sound_button >= 0:
            grid = Gtk.Grid()
            grid.set_column_spacing(4)
            self.circle_number = CircleNumber(Config.joystick.sound_button,
                                              circle_pixbuf)
            grid.add(self.circle_number)
            grid.add(name_label)
            self.label = grid
        else:
            self.label = name_label
        self.set_active(False)
        self.connect("notify::active", self.engine_toggled)
        self.sound_controller = sound_controller
        self.speed_scale = speed_scale
        
    def engine_toggled(self, switch, is_active):
        loco_speed = self.speed_scale.get_value()
        if self.get_active() and not self.sound_controller.get_engine_is_running():
            if loco_speed == 0:
                self.perform_engine_startup()
            else:
                self.sound_controller.start_engine_at_speed(loco_speed)
            self.set_fill_level(loco_speed)
                    
        elif not self.get_active() and self.sound_controller.get_engine_is_running():
            if loco_speed == 0:
                self.perform_engine_shutdown()
            else:
                self.sound_controller.stop_engine()
            self.reset_fill_level()
            
    def perform_engine_startup(self):
        """
        Make *self.sound_controller* play the
        engine-startup-sounds (if any).
        To be implemented in a child class.
        """
        raise NotImplementedError()
        
    def perform_engine_shutdown(self):
        """
        Make *self.sound_controller* play the
        engine-shutdown-sounds (if any).
        To be implemented in a child class.
        """
        raise NotImplementedError()
    
    def set_fill_level(self, loco_speed):
        """
        Set the fill-level of *self.speed_scale*
        so that it matches the sound played at
        *loco_speed*.
        To be implemented in a child class.
        """
        raise NotImplementedError()
    
    def reset_fill_level(self):
        """
        Set the fill-level of *self.speed_scale* back
        to 0. To be implemented in a child class.
        """
        raise NotImplementedError()

class DieselEngineSwitch(EngineSwitch):
    """
    :class:`EngineSwitch`-implementation for the needs of
    :class:`DieselEngine`.
    """
    def __init__(self, sound_controller, speed_scale, sound_circle):
        EngineSwitch.__init__(self,
                              sound_controller,
                              speed_scale,
                              sound_circle)
        self.grid = Gtk.Grid()
        self.grid.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.grid.set_column_spacing(5)
        self.grid.set_halign(Gtk.Align.CENTER)
        self.grid.add(self.label)
        self.add(self.grid)
        
        self.spinner = Gtk.Spinner()
        self.spinner.show()
        
    def set_fill_level(self, loco_speed):
        # allow animations to start again
        self.speed_scale.ignore_sound_changes = False
        if loco_speed != 0:
            sound_func = self.sound_controller.engine.sound_function
            self.speed_scale.set_fill_level(sound_func.segments[sound_func.get_segment_nr_from_x(loco_speed)].end)
        
    def reset_fill_level(self):
        # prevent further animations from starting
        self.speed_scale.ignore_sound_changes = True
        if hasattr(self.speed_scale, "animator") \
        and not self.speed_scale.animator.stop_event.is_set():
#             locked_print("speed-scale is animating, stopping it")
            self.speed_scale.animator.stop_event.set()
        self.speed_scale.set_fill_level(0)
        
    def perform_engine_startup(self):
        self.start_spinner()
        self.idle_handler_id = self.sound_controller.connect("engine-idle",
                                                             self.finished_starting_engine)
        self.sound_controller.start_engine()
        
    def perform_engine_shutdown(self):
        # quit engine when it is idle!
        self.idle_handler_id = self.sound_controller.connect("engine-idle",
                                                             self.shutdown_engine)
        GObject.idle_add(self.start_spinner)
        
    def shutdown_engine(self, sound_controller):
        sound_controller.disconnect(self.idle_handler_id)
        self.stopped_handler_id = self.sound_controller.connect("engine-stopped",
                                                                self.finished_stopping_engine)
        sound_controller.shutdown_engine()
        
    def finished_stopping_engine(self, sound_controller):
        sound_controller.disconnect(self.stopped_handler_id)
        self.stop_spinner()
        
    def finished_starting_engine(self, sound_controller):
        sound_controller.disconnect(self.idle_handler_id)
        self.stop_spinner()
        
    def start_spinner(self):
        self.spinner.start()
        self.grid.add(self.spinner)
        self.speed_scale.set_sensitive(False)
        self.set_sensitive(False)
        if hasattr(self, "circle_number"):
            # needed for some themes, otherwise the
            # "transparent"-property gets lost and it looks ugly
            self.circle_number.queue_draw()
        
    def stop_spinner(self):
        self.grid.remove(self.spinner)
        self.spinner.stop()
        self.speed_scale.set_sensitive(True)
        self.set_sensitive(True)
        if hasattr(self, "circle_number"):
            self.circle_number.queue_draw()

class SteamEngineSwitch(EngineSwitch):
    """
    :class:`EngineSwitch`-implementation for the needs of
    :class:`SteamEngine`.
    """
    def __init__(self, sound_controller, speed_scale, sound_circle):
        EngineSwitch.__init__(self,
                              sound_controller,
                              speed_scale,
                              sound_circle)
        self.add(self.label)
        
    def set_fill_level(self, loco_speed):
        self.speed_scale.set_fill_level(loco_speed)
        
    def reset_fill_level(self):
        self.speed_scale.set_fill_level(0)
        
    def perform_engine_startup(self):
        self.sound_controller.start_engine()
        
    def perform_engine_shutdown(self):
        self.sound_controller.shutdown_engine()

class CircleNumber(Gtk.Overlay):
    """
    A :class:`Gtk.Overlay` which shows an integer
    *nr* on top of a colored *circle_pixbuf*.
    Used to label loco-function buttons with their
    corresponding gamepad button.
    """
    size = 22
    def __init__(self, nr, circle_pixbuf):
        Gtk.Overlay.__init__(self)
        circle = Gtk.Image()
        circle.set_from_pixbuf(circle_pixbuf.scale_simple(self.size,
                                                          self.size,
                                                          GdkPixbuf.InterpType.BILINEAR))
        self.add(circle)
        
        nr_label = Gtk.Label()
        nr_label.set_halign(Gtk.Align.CENTER)
        nr_label.set_valign(Gtk.Align.CENTER)
        nr_label.set_markup("<b>" + str(nr) + "</b>")
        self.add_overlay(nr_label)
        
        try:
            self.get_style_context().add_class("transparent")
#             nr_label.get_style_context().add_class("transparent")
        except:
            pass

class FunctionButton(Gtk.ToggleButton):
    """
    
    """
    def __init__(self, function, circle_pixbuf):
        Gtk.ToggleButton.__init__(self)
        # every kind of function-button has the attribute 'function'
        # and a unique attribute (e.g. 'function_sound')
        # -> both are the same, 2nd exists for readability
        self.function = function
        
        self.set_size_request(100, 30)
        
        label = Gtk.Label(function.name)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_halign(Gtk.Align.CENTER)
        
        # values less than 0 mean there is no func-button
        if Config.joystick.show_function_nr and function.button >= 0:
            grid = Gtk.Grid()
            grid.set_column_spacing(4)
            self.circle_number = CircleNumber(function.button, circle_pixbuf)
            grid.add(self.circle_number)
            grid.add(label)
            self.add(grid)
        else:
            self.add(label)
               
        self.set_tooltip_text(function.name)
        
        if function.state:
            self.set_active(True)
        self.connect("clicked", self.toggle_function)

class LocoFunctionButton(FunctionButton):
    def __init__(self, loco, function, circle_pixbuf, socket_thread):
        FunctionButton.__init__(self, function, circle_pixbuf)
        self.loco = loco
        self.socket_thread = socket_thread
        
    def toggle_function(self, button):
        self.function.toggle()
        self.socket_thread.send_and_wait_for_answer(self.loco.get_srcp_status(Config.server.bus))
#         locked_print("Funktion",
#                      self.function.name,
#                      "von Lok",
#                      self.loco.name,
#                      "wurde " + {True: "an", False: "aus"}[self.function.state] +
#                      "geschaltet.")

class FunctionSoundButton(FunctionButton):
    def __init__(self, function_sound, circle_pixbuf, mixer, channel_id):
        FunctionButton.__init__(self, function_sound, circle_pixbuf)
        self.function_sound = function_sound
        self.mixer = mixer
        self.channel_id = channel_id
        if self.function_sound.toggle_mode == config.ToggleMode.TAP:
            mixer.add_callback(function_sound.channel_id, self.clicked)
        if self.function_sound.state:
            self.check_queue_sound()
        
    def toggle_function(self, button):
        self.function_sound.toggle()
        self.check_queue_sound()
        
    def check_queue_sound(self):
        if self.function_sound.state:
            self.mixer.queue_sound(self.channel_id,
                                   self.function_sound.sound)
            if self.function_sound.toggle_mode in [config.ToggleMode.SWITCH,
                                                   config.ToggleMode.PUSH]:
                # queue second time for gapless looping
                self.mixer.queue_sound(self.channel_id, self.function_sound.sound)
            elif self.function_sound.toggle_mode == config.ToggleMode.TAP:
                self.set_sensitive(False)
                if hasattr(self, "circle_number"):
                    # needed for some themes, otherwise the "transparent"-property
                    # gets lost and it looks ugly
                    self.circle_number.queue_draw()
        else:
            self.mixer.channels[self.channel_id].stop()
            if self.function_sound.toggle_mode == config.ToggleMode.TAP:
                self.set_sensitive(True)
                if hasattr(self, "circle_number"):
                    self.circle_number.queue_draw()
#         locked_print("Geräusch-Funktion",
#                      self.function_sound.name,
#                      "hat nun den Status",
#                      self.function_sound.state)
        
class EventSoundButton(FunctionButton):
    def __init__(self, event_sound, circle_pixbuf, channel):
        FunctionButton.__init__(self, event_sound, circle_pixbuf)
        self.event_sound = event_sound
        self.channel = channel
        
    def toggle_function(self, button):
        self.event_sound.toggle()
        if not self.event_sound.state:
            self.channel.stop()
#         locked_print("Geräusch-Ereignis",
#                      self.function.name,
#                      "hat nun den Status",
#                      self.function.state)
            
class FunctionBox(Gtk.Grid):
    def __init__(self,
                 loco,
                 speed_scale,
                 event_thread,
                 socket_thread,
                 circle_pixbufs):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_halign(Gtk.Align.CENTER)
        self.buttons = [LocoFunctionButton(loco,
                                           function,
                                           circle_pixbufs["loco_function"],
                                           socket_thread) for function in loco.functions]
        self.boxes = []
        self.nr_rows = 0
        
        if pygame_io.pygame_installed:
            # we need func-nr in the whole method,
            # therefore it must be declared here
            func_nr = 0
            if loco.function_sounds != None:
                # add the needed 'sound' and 'channel_id'
                # attribs to the func-sound-objs
                pygame_io.prepare_function_sounds(event_thread,
                                                  loco.function_sounds,
                                                  loco.sound_volume)
                for func_nr, function_sound in enumerate(loco.function_sounds):
                    self.buttons.insert(func_nr, 
                                        FunctionSoundButton(function_sound,
                                                            circle_pixbufs["function_sound"],
                                                            event_thread,
                                                            function_sound.channel_id))
            
            if loco.engine != None:
                self.sound_switch = create_engine_switch(loco.engine.type,
                                                         loco.sound_controller,
                                                         speed_scale,
                                                         circle_pixbufs["speed_sound"])
                for ev_nr, event_sound in enumerate(loco.engine.event_sounds):
                    self.buttons.insert(ev_nr + func_nr + 1,
                                        EventSoundButton(event_sound,
                                                         circle_pixbufs["event_sound"],
                                                         event_thread.channels[event_sound.channel_id]))
                self.buttons.insert(0, self.sound_switch)
        
        nr_buttons = len(self.buttons)

        if nr_buttons > 0:            
            # estimate the number of columns needed
            nr_columns, rest_columns = divmod(nr_buttons, 5)
            if rest_columns > 0:
                nr_columns += 1
            
            # estimate the nr of buttons per box if the buttons are equally spread
            buttons_per_column, rest_buttons = divmod(nr_buttons, nr_columns)
            if rest_buttons > 0:
                buttons_per_column += 1
                
            nr_buttons_left = nr_buttons
            for unused_col_nr in xrange(nr_columns):
                box = FunctionButtonBox()
                
                if nr_buttons_left > buttons_per_column:
                    nr_buttons_to_pack = buttons_per_column
                else:
                    nr_buttons_to_pack = nr_buttons_left
                
                for row in xrange(nr_buttons_to_pack):
                    box.pack_start(self.buttons[nr_buttons - nr_buttons_left + row],
                                   True,
                                   True,
                                   0)
                
                if nr_buttons_to_pack > self.nr_rows:
                    self.nr_rows = nr_buttons_to_pack
                
                nr_buttons_left -= nr_buttons_to_pack
                self.boxes.append(box)
                self.add(box)
          
class FunctionButtonBox(Gtk.ButtonBox):
    def __init__(self):
        Gtk.ButtonBox.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_layout(Gtk.ButtonBoxStyle.CENTER)
        self.set_valign(Gtk.Align.START)
        # TODO: uncomment when gtk-themes can do that in future
        # (make the boxes appear as one nice unit)
#        context = self.get_style_context()
#        context.add_class(Gtk.STYLE_CLASS_LINKED)
        self.set_homogeneous(True)

class EmergencyButton(Gtk.ToggleButton):
    """
    Button controlling the power on the tracks represented
    by ``JsonModel.server.bus``.
    """
    def __init__(self, socket_thread):
        Gtk.ToggleButton.__init__(self)
        self.set_name("emergency-button")
        
        self.set_label("Nothalt")
        self.set_size_request(-1 , 50)
        self.socket_thread = socket_thread
        
        if not Config.server.power:
            self.set_active(True)
        self.send_power()
        
        self.connect("clicked", self.toggle_power)
    
    def toggle_power(self, *args):
        Config.server.toggle_power()
        self.send_power()
        
    def send_power(self):
        if Config.server.power:
            self.socket_thread.send_and_wait_for_answer("SET " +
                                                        str(Config.server.bus) +
                                                        " POWER ON\n")
#             locked_print("\nStrom angeschaltet")
        else:
            self.socket_thread.send_and_wait_for_answer("SET " +
                                                        str(Config.server.bus) +
                                                        " POWER OFF\n")
#             locked_print("\nNotstop eingeleitet")
