#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

from gi.repository.GLib import GError
from gi.repository import GObject, Gtk, Pango, GdkPixbuf

import socket
import threading
import time

from electrip.concurrent import locked_print, SocketThread
from electrip import pygame_io
from electrip import config
from electrip.constants import SOUND_LEVEL_ANIM_RES
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
        # -------- Handshake ----------
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
        # add event-box for custom background
        event_box = Gtk.EventBox()
        event_box.set_name("loco-controller-hub-bg")
        event_box.add(self.controller_hub)
        self.add_with_viewport(event_box)


class ControllerHub(Gtk.Grid):
    """
    :class:`Gtk.Grid` which fills itself with :class:`LocoController`-
    instances. Responsible for creating a :class:`EventHandlerThread`
    and taking over gamepad-event-handling via
    :func:`EventHandlerThread.gamepad_init` if pygame is available.
    """
    spacing = 6

    def __init__(self, socket_thread, emergency_button, h_adjustment):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_column_spacing(self.spacing)
        self.set_property("margin", self.spacing)

        self.emergency_button = emergency_button
        self.h_adjustment = h_adjustment

        gamepads_exist = False
        if pygame_io.pygame_installed:
            # pygame is available, thus gamepads may be used
            # 1. create event-thread and connect event handlers
            self.event_thread = pygame_io.EventHandlerThread(Config.sound.sampling_rate)
            if self.event_thread.gamepad_init(self.gamepad_button_pressed,
                                              self.gamepad_button_released,
                                              self.horiz_joyhat_moved,
                                              self.axis_released,
                                              len(Config.locos)) > 0:
                # if the nr of gamepads we can use is > 0 we proceed:
                gamepads_exist = True

                # 2. mapping allows us to track which loco belongs to which gamepad
                self.mapping = TwoWayDict()
                for loco_id, gmp in enumerate(self.event_thread.gamepads):
                    self.mapping[gmp] = loco_id

                self.accel_timeout_id = GObject.timeout_add(50, self.check_acceleration)

            self.event_thread.start()
        else:
            self.event_thread = None

        func_size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.VERTICAL)

        # create an iterator we can use to retrieve the gamepads
        # one by one in the for-loop
        if pygame_io.pygame_installed:
            gamepads = iter(self.event_thread.gamepads)
        else:
            gamepads = iter([])

        self.controllers = []
        for loco in Config.locos:
            controller = LocoController(socket_thread,
                                        loco,
                                        func_size_group,
                                        gamepads_exist,
                                        next(gamepads, None),
                                        self.event_thread)
            self.controllers.append(controller)
            self.add(controller)

    def focus_controller(self, controller):
        allocation = controller.get_allocation()
        self.h_adjustment.clamp_page(allocation.x - self.spacing,
                                     allocation.x + allocation.width + self.spacing)

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
            self.focus_controller(self.controllers[loco_id])

        elif button == Config.joystick.sound_button \
        and self.controllers[loco_id].loco.engine:
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
        gamepad.scroll_direction = direction

        if direction in (1, -1):
            # scroll one position in 'direction'
            self.scroll(direction, gamepad)
            # after 500 ms, check if auto-scrolling should be enabled
            self.timeout_handle = GObject.timeout_add(500,
                                                      self.set_auto_scroll,
                                                      direction,
                                                      gamepad)
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
                if new_loco_id not in self.mapping:
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
        self.controllers[loco_id].set_gamepad(None)
        self.controllers[new_loco_id].set_gamepad(gamepad)

        # if auto-focus is active, make the controller focus itself in the window
        # using GObject.idle_add makes this work fluidly
        if Config.joystick.use_auto_focus:
            GObject.idle_add(self.focus_controller, self.controllers[new_loco_id])

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

    def axis_released(self, gamepad, axis):
        """
        Sets the acceleration of the loco corresponding
        to *gamepad* to 0 if *axis* is responsible for
        loco acceleration. This ensures the event_sounds of
        the loco behave properly.
        """
        if axis == Config.joystick.accel_axis:
            Config.locos[self.mapping[gamepad]].acceleration = 0

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
                    scale.set_value(self.accelerate_loco(Config.locos[self.mapping[gamepad]],
                                                         axis_value))
        return True

    @staticmethod
    def accelerate_loco(loco, value):
        """
        Calculates the acceleration of *loco* using *value*,
        which must be a float between -1 and 1 representing the
        acceleration rate.
        If *value* is positive, the loco is accelerated
        with respect to ``loco.accel_duration``, if negative
        ``loco.decel_duration``.
        Returns the resulting speed of the loco.
        """
        if value >= 0:
            accel = value * (0.05 / loco.accel_duration * loco.max_speed)

        else:
            accel = value * (0.05 / loco.decel_duration * loco.max_speed)
        return min(loco.max_speed,
                   max(0, loco.speed + accel))

    def quit(self):
        if hasattr(self, "accel_timeout_id"):
            GObject.source_remove(self.accel_timeout_id)
        if self.event_thread:
            self.event_thread.quit()


class LocoController(Gtk.Frame):
    """
    Widget allowing to control a *loco*, using a speed-scale,
    a reverser-button and function-buttons.
    Also shows a loco-image as well as an image visualizing
    the gamepad which is currently controlling the loco.
    """
    def __init__(self,
                 socket_thread,
                 loco,
                 func_size_group,
                 gamepads_exist,
                 gamepad,
                 event_thread=None):
        Gtk.Frame.__init__(self)
        self.set_halign(Gtk.Align.CENTER)
        self.get_style_context().add_class("loco-controller")

        if gamepads_exist:
            if gamepad:
                self.get_style_context().add_class("has-gamepad")
                self.get_style_context().add_class("has-gamepad-" + str(gamepad.pygame_id))
                self.gamepad_label = Gtk.Label.new(gamepad.name)
            else:
                self.gamepad_label = Gtk.Label.new("")
            self.gamepad_label.get_style_context().add_class("gamepad-label")
            self.gamepad_label.set_ellipsize(Pango.EllipsizeMode.END)
            self.gamepad_label.hide()
            self.set_label_align(0.5, 0.0)
            self.set_label_widget(self.gamepad_label)

        self.loco = loco
        self.loco_image = LocoImage(loco.img_path)
        self.gamepad = gamepad

        if loco.engine and event_thread:
            loco.sound_controller = pygame_io.create_sound_controller(loco.engine.type,
                                                                      event_thread,
                                                                      loco.engine,
                                                                      loco.sound_volume)
            pygame_io.EventSoundPlayer(loco, event_thread)
            pygame_io.FunctionSoundPlayer(loco, event_thread)
            engine_type = loco.engine.type
        else:
            loco.sound_controller = None
            engine_type = None

        self.speed_scale = create_speed_scale(engine_type,
                                              loco,
                                              socket_thread,
                                              loco.sound_controller)

        self.reverser = Reverser(loco, socket_thread, self.speed_scale)

        self.function_box = FunctionBox(self.loco,
                                        self.speed_scale,
                                        event_thread,
                                        socket_thread)
        bg_frame = Gtk.Frame()
        bg_frame.get_style_context().add_class("function-box-bg")
        bg_frame.add(self.function_box)
        func_size_group.add_widget(self.function_box)

        grid = Gtk.Grid()
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        grid.add(self.loco_image)
        grid.add(self.speed_scale)
        grid.add(Gtk.Label.new("km/h"))
        grid.add(self.reverser)
        grid.add(bg_frame)

        self.add(grid)

    def set_gamepad(self, new_gamepad):
        """
        Styles itself using CSS to highlight the
        *new_gamepad* which is now in control.
        """
        if self.gamepad:
            self.get_style_context().remove_class("has-gamepad")
            self.get_style_context().remove_class("has-gamepad-" + str(self.gamepad.pygame_id))
            self.gamepad_label.set_text("")
        if new_gamepad:
            self.gamepad_label.set_text(new_gamepad.name)
            self.get_style_context().add_class("has-gamepad")
            self.get_style_context().add_class("has-gamepad-" + str(new_gamepad.pygame_id))
        self.gamepad = new_gamepad


class LocoImage(Gtk.Image):
    """
    Image using *path* as file-path, scaling down
    to 110x85 pixels automatically.
    """
    def __init__(self, path):
        Gtk.Image.__init__(self)
        self.set_size_request(110, 85)
        if path is None:
            self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
        else:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path) \
                            .scale_simple(110, 85, GdkPixbuf.InterpType.BILINEAR)
            except GError:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file("icons/question_mark.svg")
                locked_print("Dateipfad '" + path + "' für Lokbild ist ungültig.")
            finally:
                self.set_from_pixbuf(pixbuf)


def create_speed_scale(engine_type, *args):
    if engine_type is None:
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
        self.get_style_context().add_class("loco-speed-scale")

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

    def speed_changed(self, scale, unused_sound_controller):
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
                and self.stop_handler_id is None:
                    self.stop_handler_id = sound_controller.connect("engine-idle",
                                                                    self.stop_loco)
                elif self.loco.last_speed_step == 0 \
                and self.start_handler_id is None:
                    self.start_handler_id = self.connect("started-driving",
                                                         self.start_loco)
            if self.start_handler_id == self.stop_handler_id is None:
                self.send_srcp()
        if sound_controller.get_engine_is_running():
            sound_controller.set_target_speed(self.loco.speed)

    # synchronize loco-speed with sound (loco does stop/start when sound is ready)
    def stop_loco(self, sound_controller):
        if int(self.loco.speed_step) == 0:
            self.send_srcp()
        sound_controller.disconnect(self.stop_handler_id)
        self.stop_handler_id = None

    def start_loco(self, diesel_speed_scale):
        if int(self.loco.speed_step) != 0:
            self.send_srcp()
        self.disconnect(self.start_handler_id)
        self.start_handler_id = None

    def animate_fill_level(self, animator, sound_level, sound_length, last_time=None):
        if not self.ignore_sound_changes:
            if last_time is None:
                if sound_level == 0 and self.loco.last_speed_step == 0:
                    self.emit("started-driving")
            else:
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
                        self.animate_with_args(0, sound_length)
                    else:
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
    def __init__(self, loco_name):
        Gtk.Label.__init__(self)
        self.get_style_context().add_class("loco-label")

        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_text(loco_name)
        self.set_width_chars(min(len(loco_name), 15))
        self.set_margin_top(7)


class Reverser(Gtk.ToggleButton):
    """
    Button which toggles the direction of the loco.
    """
    def __init__(self, loco, socket_thread, scale):
        Gtk.ToggleButton.__init__(self)
        self.get_style_context().add_class("reverser")
        self.set_hexpand(True)

        # all the state logic is covered in 'styles.css'

        arrow_left = Gtk.Image()
        arrow_left.set_size_request(30, 30)
        arrow_left.set_valign(Gtk.Align.CENTER)
        arrow_left.get_style_context().add_class("left-arrow")

        arrow_right = Gtk.Image()
        arrow_right.set_size_request(30, 30)
        arrow_right.set_valign(Gtk.Align.CENTER)
        arrow_right.get_style_context().add_class("right-arrow")

        grid = Gtk.Grid()
        grid.set_orientation(Gtk.Orientation.HORIZONTAL)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_column_spacing(5)
        grid.set_margin_top(5)
        grid.set_margin_bottom(5)
        grid.add(arrow_left)
        grid.add(LocoLabel(loco.name))
        grid.add(arrow_right)
        self.add(grid)

        if loco.direction:
            self.set_active(True)
        else:
            self.get_style_context().add_class("point-left")

        # connect at the end, to avoid a wrong call
        # of loco.toggle_direction
        self.connect("toggled", self.toggle_direction, loco,
                     socket_thread, scale)

    def toggle_direction(self, unused_grid, loco,
                         socket_thread, scale):
        loco.toggle_direction()
        # if direction has changed but speed is already 0
        if int(loco.speed_step) == 0:
            socket_thread.send_and_wait_for_answer(loco.get_srcp_status(Config.server.bus))
        # if speed != 0, scale will send the change over the socket 
        scale.set_value(0)

        context = self.get_style_context()
        if loco.direction:
            context.remove_class("point-left")
        else:
            context.add_class("point-left")


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
    Creates *self.label* (showing a circle in the background if
    ``JsonModel.joystick.show_function_nr == True``).
    """
    def __init__(self, sound_controller, speed_scale):
        Gtk.ToggleButton.__init__(self)
        self.get_style_context().add_class("function-button")
        self.get_style_context().add_class("engine-switch")

        name_label = Gtk.Label("Fahrgeräusch")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)

        if Config.joystick.show_function_nr \
        and Config.joystick.sound_button >= 0:
            grid = Gtk.Grid()
            grid.set_column_spacing(5)
            self.circle_number = CircleNumber(Config.joystick.sound_button)
            grid.add(self.circle_number)
            grid.add(name_label)
            self.label = grid
        else:
            self.label = name_label
        self.add(self.label)
        self.set_active(False)
        self.connect("notify::active", self.engine_toggled)
        self.sound_controller = sound_controller
        self.speed_scale = speed_scale

        self.set_valign(Gtk.Align.START)

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
    def __init__(self, sound_controller, speed_scale):
        EngineSwitch.__init__(self,
                              sound_controller,
                              speed_scale)
#         self.grid = Gtk.Grid()
#         self.grid.set_orientation(Gtk.Orientation.HORIZONTAL)
#         self.grid.set_column_spacing(5)
#         self.grid.add(self.label)

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
        self.label.add(self.spinner)
        self.speed_scale.set_sensitive(False)
        self.set_sensitive(False)
        if hasattr(self, "circle_number"):
            # needed for some themes, otherwise the
            # "transparent"-property gets lost and it looks ugly
            self.circle_number.queue_draw()

    def stop_spinner(self):
        self.label.remove(self.spinner)
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
    def __init__(self, sound_controller, speed_scale):
        EngineSwitch.__init__(self,
                              sound_controller,
                              speed_scale)

    def set_fill_level(self, loco_speed):
        self.speed_scale.set_fill_level(loco_speed)

    def reset_fill_level(self):
        self.speed_scale.set_fill_level(0)

    def perform_engine_startup(self):
        self.sound_controller.start_engine()

    def perform_engine_shutdown(self):
        self.sound_controller.shutdown_engine()


class CircleNumber(Gtk.Label):
    """
    A :class:`Gtk.Label` which shows an integer
    *nr* inside a circle (styled using CSS).
    """
    size = 22

    def __init__(self, nr):
        Gtk.Label.__init__(self)
        self.get_style_context().add_class("circle-number")

        self.set_size_request(self.size, self.size)
        self.set_text(str(nr))


class FunctionButton(Gtk.ToggleButton):
    """
    Base class for Buttons which toggle loco functions.
    *function* must be a :class:`LocoFunction`.
    """
    def __init__(self, function):
        Gtk.ToggleButton.__init__(self)
        self.get_style_context().add_class("function-button")

        # every kind of function-button has the attribute 'function'
        # and a unique attribute (e.g. 'function_sound')
        # -> both are the same, 2nd exists for readability
        self.function = function
        self.set_valign(Gtk.Align.START)

        label = Gtk.Label(function.name)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_width_chars(10)

        # values less than 0 mean there is no func-button
        if Config.joystick.show_function_nr and function.button >= 0:
            grid = Gtk.Grid()
            grid.set_column_spacing(5)
            self.circle_number = CircleNumber(function.button)
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
    def __init__(self, loco, function, socket_thread):
        FunctionButton.__init__(self, function)
        self.loco = loco
        self.socket_thread = socket_thread

    def toggle_function(self, button):
        self.function.toggle()
        self.socket_thread.send_and_wait_for_answer(self.loco.get_srcp_status(Config.server.bus))


class FunctionSoundButton(FunctionButton):
    def __init__(self, function_sound, handler_thread):
        FunctionButton.__init__(self, function_sound)
        self.get_style_context().add_class("function-sound-button")
        self.function_sound = function_sound
        if self.function_sound.toggle_mode == config.ToggleMode.TAP:
            handler_thread.add_callback(function_sound.channel_id, self.clicked)

    def toggle_function(self, button):
        self.function_sound.toggle()
        if self.function_sound.toggle_mode == config.ToggleMode.TAP:
            if self.function_sound.state:
                self.set_sensitive(False)
            else:
                self.set_sensitive(True)


class EventSoundButton(FunctionButton):
    def __init__(self, event_sound):
        FunctionButton.__init__(self, event_sound)
        self.get_style_context().add_class("event-sound-button")
        self.event_sound = event_sound

    def toggle_function(self, button):
        self.event_sound.toggle()


class FunctionBox(Gtk.Grid):
    def __init__(self,
                 loco,
                 speed_scale,
                 event_thread,
                 socket_thread):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_halign(Gtk.Align.CENTER)
        self.set_column_spacing(3)
        self.set_row_spacing(3)

        size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.BOTH)

        self.buttons = [LocoFunctionButton(loco,
                                           function,
                                           socket_thread) for function in loco.functions]
        self.nr_rows = 0

        if pygame_io.pygame_installed:
            if loco.function_sounds:
                # add the needed 'sound' and 'channel_id'
                # attributes to the func-sound-objects
                pygame_io.prepare_function_sounds(event_thread,
                                                  loco.function_sounds,
                                                  loco.sound_volume)
                for func_nr, function_sound in enumerate(loco.function_sounds):
                    self.buttons.insert(func_nr,
                                        FunctionSoundButton(function_sound,
                                                            event_thread))
            if loco.event_sounds:
                for ev_nr, event_sound in enumerate(loco.event_sounds):
                    self.buttons.insert(ev_nr,
                                        EventSoundButton(event_sound))

            if loco.engine:
                self.sound_switch = create_engine_switch(loco.engine.type,
                                                         loco.sound_controller,
                                                         speed_scale)
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
            for col_nr in xrange(nr_columns):
                if nr_buttons_left > buttons_per_column:
                    nr_buttons_to_pack = buttons_per_column
                else:
                    nr_buttons_to_pack = nr_buttons_left

                for row_nr in xrange(nr_buttons_to_pack):
                    button = self.buttons[nr_buttons - nr_buttons_left + row_nr]
                    size_group.add_widget(button)
                    self.attach(button, col_nr, row_nr, 1, 1)

                if nr_buttons_to_pack > self.nr_rows:
                    self.nr_rows = nr_buttons_to_pack

                nr_buttons_left -= nr_buttons_to_pack


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
        else:
            self.socket_thread.send_and_wait_for_answer("SET " +
                                                        str(Config.server.bus) +
                                                        " POWER OFF\n")
