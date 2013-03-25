#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository.GLib import GError
from gi.repository import GObject, Gtk, Pango, GdkPixbuf
import socket
from LockedPrint import locked_print, SocketRecvThread
from Pygame import JoystickAndSound
from Pygame.JoystickAndSound import FunctionSoundController
from Constants import EngineType, ToggleMode, CIRCLE_PATHS, \
    SOUND_LEVEL_ANIM_RES
import threading
import time

class MainBox(Gtk.Grid):    
    def __init__(self, config_copy):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        global Config
        Config = config_copy
        Config.notice_unsaved_changes = False
        
        self.socket_init()
        self.event_thread = JoystickAndSound.EventHandlerThread(Config)
        self.scrolled_window = ScrolledWindow(self.socket, self) # ScrolledWindow und darin HBox für Controller erzeugen
        self.emergency_button = EmergencyButton(self.socket) # HBox für Notstop erzeugen
        self.add(self.scrolled_window)
        self.add(self.emergency_button)
        try:
            self.event_thread.joystick_init(self.scrolled_window.center_grid.controllers, self.emergency_button)
            self.event_thread.start()
        except NameError:
            locked_print("Konnte pygame-Threads nicht starten, Joysticks werden nicht erkannt.")
        self.show_all()
    
    def quit(self):
        self.event_thread.quit()
        self.socket.send("TERM 1 POWER\n")
        self.socket.send("TERM 0 SESSION\n")
        self.socket_thread.quit()
        locked_print("Steuerung geschlossen.")
        self.destroy()
    
    def socket_init(self):
        bus = str(Config.server.bus)
        # Create Socket-Connection
        self.socket = socket.create_connection((Config.server.host, Config.server.port))
        #-------- Handshake ----------
        locked_print("Socketverbindung aktiv mit:")
        locked_print(self.socket.recv(4096))
        
        self.socket.send("SET CONNECTIONMODE SRCP COMMAND\n")
        locked_print("Connectionmode 'Command' wird angefordert:")
        locked_print(self.socket.recv(4096))
        
        self.socket.send('GO\n')
        locked_print("Es kann losgehen, was sagt der Server?")
        locked_print(self.socket.recv(4096))
        
        # -------- Initialize Power on Server-Bus ---------
        self.socket.send("INIT " + bus + " POWER\n")
        locked_print(self.socket.recv(4096))
        
        # ---------- Initialize Locos -------------
        for loco in Config.locos:
            if len(loco.functions) > 0: # nr_functions_to_send is NOT the same as len(loco.functions), but the highest decoder-function-nr
                nr_functions_to_send = max(function.nr + 1 for function in loco.functions)
            else:
                nr_functions_to_send = 0
            text = "INIT " + bus + " GL " + str(loco.address) + " " + str(loco.protocol) + " " + str(int(loco.speed_steps)) + " " + str(nr_functions_to_send) + "\n"
            locked_print(text)
            self.socket.send(text)
            locked_print(self.socket.recv(4096))
            self.socket.send(loco.get_srcp_status(Config.server.bus))
            locked_print(self.socket.recv(4096))

        self.socket_thread = SocketRecvThread(self.socket) # Nach dem Handshake und Loco-Init wird der Receive in einen separaten Thread verlegt -> keine MainWindow-Blockierungen möglich
        self.socket_thread.start()
        
class ScrolledWindow(Gtk.ScrolledWindow):
    def __init__(self, socket, main_window):
        Gtk.ScrolledWindow.__init__(self)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.center_grid = CenterGrid(socket, main_window, self)
        self.add_with_viewport(self.center_grid)
        
class CenterGrid(Gtk.Grid):
    def __init__(self, socket, main_window, scrolled_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_column_spacing(8)
        self.set_margin_bottom(8)
        self.controllers = []
        self.socket = socket
        for i, loco in enumerate(Config.locos): # Alle Controller hinzufügen
            self.controllers.append(Controller(socket, loco, scrolled_window, main_window.event_thread))
            self.add(self.controllers[i])
        self.connect("realize", self.realized, main_window.event_thread)
                
    def realized(self, hbox, event_thread):
        max_height = 0
        max_label_width = 0
        config_has_functions = False
        circle_pixbufs = dict([(name, GdkPixbuf.Pixbuf.new_from_file(path)) for name, path in CIRCLE_PATHS.items()])
        
        for controller in self.controllers:
            controller.function_box = FunctionBox(controller.loco, controller.speed_scale, event_thread, self.socket, circle_pixbufs)
            controller.function_box.show_all()
            controller.add(controller.function_box)
            height = controller.function_box.get_preferred_height()[1]
            if height > max_height:
                max_height = height
            if not config_has_functions and len(controller.function_box.buttons) > 0:
                config_has_functions = True
            width = controller.loco_label.get_preferred_width()[1]
            if width > max_label_width:
                max_label_width = width
        
        if config_has_functions: # if there are no functions, we dont need to do special size-requests
            for controller in self.controllers:
                controller.function_box.set_size_request(-1, max_height)
                if controller.get_preferred_width()[1] <= max_label_width:
                    controller.set_size_request(max_label_width, -1) # if the label-width of another controller is bigger than controllers width, request size -> nicer layout

class Controller(Gtk.Grid):
    joystick = None
    sound_controller = None
    
    def __init__(self, socket, loco, scrolled_window, event_thread):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(True)
        self.loco = loco
        self.loco_image = LocoImage(loco.img_path)
        if loco.engine != None:
            loco.sound_controller = JoystickAndSound.create_sound_controller(loco.engine.type, event_thread, loco.engine, loco.sound_volume)
        else:
            loco.sound_controller = None
        if loco.engine == None:
            engine_type = None
        else:
            engine_type = loco.engine.type
        self.speed_scale = create_speed_scale(engine_type, loco, socket, loco.sound_controller)
        self.loco_label = LocoLabel(loco)
        self.reverser = Reverser(loco, socket, self.speed_scale)
        self.gamepad_image = Gtk.Image()
        self.gamepad_image.set_size_request(100, 76) # TODO: find alternative! (5px bigger than image, some themes (e.g. Elementary) need this)
        self.scrolled_window = scrolled_window
        
        self.add(self.loco_image)
        self.add(self.speed_scale)
        self.add(Gtk.Label.new("km/h"))
        self.add(self.loco_label)
        self.add(self.gamepad_image)
        self.add(self.reverser)
        
    def set_focus(self): # Put the Controller in the visible area of ScrolledWindow
        adjust = self.scrolled_window.get_hadjustment()
        allocation = self.get_allocation()
        adjust.clamp_page(allocation.x, allocation.x + allocation.width)
    
class LocoImage(Gtk.Image):
    def __init__(self, path):
        Gtk.Image.__init__(self)
        self.set_size_request(110, 85)
        if path == None:
            self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
        else:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
                small_pixbuf = pixbuf.scale_simple(110, 85, GdkPixbuf.InterpType.BILINEAR)
                self.set_from_pixbuf(small_pixbuf)
            except GError:
                self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
                locked_print("Dateipfad '" + path + "' für Lokbild ist ungültig.")

def create_speed_scale(engine_type, *args):
    if engine_type == None:
        return SpeedScale(*args)
    elif engine_type == EngineType.DIESEL:
        return DieselSpeedScale(*args)
    elif engine_type == EngineType.STEAM:
        return SteamSpeedScale(*args)

class SpeedScale(Gtk.Scale):
    def __init__(self, loco, socket, sound_controller=None):
        Gtk.Scale.__init__(self)
        self.loco = loco
        self.set_restrict_to_fill_level(False)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.set_adjustment(Gtk.Adjustment(0, 0, loco.max_speed, 0.01, 0, 0))
        self.connect("value-changed", self.speed_changed, socket, sound_controller)
        self.set_inverted(True)
        self.set_digits(1)
        self.set_value_pos(Gtk.PositionType.BOTTOM)
        
    def send_srcp(self, socket):
        socket.send(self.loco.get_srcp_status(Config.server.bus))
        locked_print("Lok", self.loco.name, "fährt jetzt", self.loco.speed, "km/h, das entspricht", int(self.loco.speed_step), "Fahrstufen.")
        
    def speed_changed(self, scale, socket, sound_controller):
        self.loco.speed = self.get_value()
        self.loco.speed_step = self.loco.speed_to_step_func.get_y(self.loco.speed)
        if int(self.loco.speed_step) != self.loco.last_speed_step:
            self.send_srcp(socket)

class DieselSpeedScale(SpeedScale):
    stop_handler_id = start_handler_id = None
    ignore_sound_changes = False
    __gsignals__ = {
      "started-driving": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
    def __init__(self, loco, socket, sound_controller=None):
        SpeedScale.__init__(self, loco, socket, sound_controller)
        sound_controller.connect("speed-changed", self.animate_fill_level)
        if Config.sound.show_level_bar:
            self.set_show_fill_level(True)
            self.set_fill_level(0)
        self.step = self.loco.max_speed / SOUND_LEVEL_ANIM_RES
    
    def speed_changed(self, scale, socket, sound_controller):
        self.loco.speed = self.get_value()
        self.loco.speed_step = self.loco.speed_to_step_func.get_y(self.loco.speed)
        real_speed_step = int(self.loco.speed_step)
        if self.loco.speed_step == 0 and self.loco.last_speed_step != 0 and self.stop_handler_id == None and sound_controller.engine_is_running:
            self.stop_handler_id = sound_controller.connect("engine-idle", self.stop_loco, socket)
        elif real_speed_step != self.loco.last_speed_step: # if speed has changed and loco didnt stand still before
            if self.loco.last_speed_step == 0 and self.start_handler_id == None and sound_controller.engine_is_running:
                self.start_handler_id = self.connect("started-driving", self.start_loco, socket)
            elif self.start_handler_id == None:
                self.send_srcp(socket)
        if sound_controller.engine_is_running:
            sound_controller.set_scheduled_speed(self.loco.speed)
    
    def stop_loco(self, sound_controller, socket): # synchronize loco-speed with sound (loco does stop/start when sound is ready)
        if int(self.loco.speed_step) == 0:
#            locked_print("--------- Stopping loco together with sound!! ---------")
            self.send_srcp(socket)
        sound_controller.disconnect(self.stop_handler_id)
        self.stop_handler_id = None
        
    def start_loco(self, diesel_speed_scale, socket):
        if int(self.loco.speed_step) != 0:
#            locked_print("--------- Starting loco together with sound!! ---------")
            self.send_srcp(socket)
        self.disconnect(self.start_handler_id)
        self.start_handler_id = None
    
    def animate_fill_level(self, animator, sound_level, sound_length, last_time=None):
        if not self.ignore_sound_changes:
            if last_time == None:
#                locked_print("Sound of diesel-loco changed to nr", sound_level, "with length", sound_length)
                if sound_level == 0 and self.loco.last_speed_step == 0:
                    self.emit("started-driving")
            else:
#                locked_print("signal received: old animator has finished")
                sound_length -= time.time() - last_time # speed up animation to make it finish in the real left time
            if Config.sound.show_level_bar:
                if hasattr(self, "animator") and not self.animator.stop_event.is_set(): # if animator lags behind played sound
                    self.animator.connect("animation-finished", self.animate_fill_level, sound_level, sound_length, time.time()) # transmit time to allow speed up in next cycle
                else:
                    if sound_level == -1:
    #                    locked_print("animating to 0")
                        self.animate_with_args(0, sound_length)
                    else:
    #                    locked_print("animating to", self.loco.engine.sound_function.segments[sound_level].end)
                        self.animate_with_args(self.loco.engine.sound_function.segments[sound_level].end, sound_length)
            
    def animate_with_args(self, sound_level, sound_length):
        start_val = self.get_fill_level()
        end_val = sound_level
        if start_val != end_val:
            self.animator = Animator(self.set_fill_level, start_val, end_val, self.step, sound_length)
            self.animator.start()

class SteamSpeedScale(SpeedScale):
    def __init__(self, loco, socket, sound_controller=None):
        SpeedScale.__init__(self, loco, socket, sound_controller)
        if Config.sound.show_level_bar:
            self.set_show_fill_level(True)
            self.set_fill_level(0)
    
    def speed_changed(self, scale, socket, sound_controller):
        self.loco.speed = self.get_value()
        self.loco.speed_step = self.loco.speed_to_step_func.get_y(self.loco.speed)
        if int(self.loco.speed_step) != self.loco.last_speed_step:
            self.send_srcp(socket)
        if sound_controller.engine_is_running:
            sound_controller.set_scheduled_speed(self.loco.speed)
            self.set_fill_level(self.loco.speed)
        
class Animator(GObject.GObject, threading.Thread):
    __gsignals__ = {
      "animation-finished": (GObject.SIGNAL_RUN_LAST, None, ()), #SIGNAL_RUN_FIRST
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
            self.sleep_time = duration / (abs(start_val - end_val) / step) # calculate sleep time for the animation
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
        GObject.idle_add(self.emit, "animation-finished")

class LocoLabel(Gtk.Label):
    def __init__(self, loco):
        self.text = loco.name
        Gtk.Label.__init__(self, self.text)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_max_width_chars(20)
        self.set_margin_top(7)

class Reverser(Gtk.Button):
    def __init__(self, loco, socket, scale):
        Gtk.Button.__init__(self)
        self.arrow_up = Gtk.Image.new_from_stock(Gtk.STOCK_GO_UP, Gtk.IconSize.BUTTON)
        self.arrow_down = Gtk.Image.new_from_stock(Gtk.STOCK_GO_DOWN, Gtk.IconSize.BUTTON)
        self.loco = loco
        self.set_arrow()
        self.connect("clicked", self.toggle_direction, socket, scale)
        self.set_hexpand(True)

    def toggle_direction(self, button, socket, scale):
        self.loco.toggle_direction()
        if int(self.loco.speed_step) == 0: # if direction has changed but speed is already 0
            socket.send(self.loco.get_srcp_status(Config.server.bus))
        scale.set_value(0)
        self.set_arrow()
        locked_print("\nLok", self.loco.name, "hat die Richtung gewechselt und fährt nun", self.loco.direction)
    
    def set_arrow(self):
        if self.loco.direction:
            self.set_image(self.arrow_up)
        else:
            self.set_image(self.arrow_down)

def create_engine_switch(engine_type, *args):
    if engine_type == EngineType.STEAM:
        return SteamEngineSwitch(*args)
    elif engine_type == EngineType.DIESEL:
        return DieselEngineSwitch(*args)

class EngineSwitch(Gtk.ToggleButton):
    def __init__(self, sound_controller, speed_scale, circle_pixbuf):
        Gtk.ToggleButton.__init__(self)
        name_label = Gtk.Label("Fahrgeräusch")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        if Config.joystick.show_function_nr and Config.joystick.sound_button >= 0:
            grid = Gtk.Grid()
            grid.set_column_spacing(4)
            self.circle_number = CircleNumber(Config.joystick.sound_button, circle_pixbuf)
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
        if self.get_active() and not self.sound_controller.engine_is_running:
            if loco_speed == 0:
                self.perform_engine_startup()
            else:
                self.sound_controller.start_engine_with_speed(loco_speed)
            self.set_fill_level(loco_speed)
                    
        elif not self.get_active() and self.sound_controller.engine_is_running:
            if loco_speed == 0:
                self.perform_engine_shutdown()
            else:
                self.sound_controller.pause_engine()
            self.reset_fill_level()

class DieselEngineSwitch(EngineSwitch):
    def __init__(self, sound_controller, speed_scale, sound_circle):
        EngineSwitch.__init__(self, sound_controller, speed_scale, sound_circle)
        self.grid = Gtk.Grid()
        self.grid.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.grid.set_column_spacing(5)
        self.grid.set_halign(Gtk.Align.CENTER)
        self.grid.add(self.label)
        self.add(self.grid)
        
        self.spinner = Gtk.Spinner()
        self.spinner.show()
        
    def set_fill_level(self, loco_speed):
        self.speed_scale.ignore_sound_changes = False # allow animations to start again
        if loco_speed != 0:
            sound_func = self.sound_controller.engine.sound_function
            self.speed_scale.set_fill_level(sound_func.segments[sound_func.get_segment_nr_from_x(loco_speed)].end)
        
    def reset_fill_level(self):
        self.speed_scale.ignore_sound_changes = True # prevent further animations from starting
        if hasattr(self.speed_scale, "animator") and not self.speed_scale.animator.stop_event.is_set():
            locked_print("speed-scale is animating, stopping it")
            self.speed_scale.animator.stop_event.set()
        self.speed_scale.set_fill_level(0)
        
    def perform_engine_startup(self):
        self.start_spinner()
        self.idle_handler_id = self.sound_controller.connect("engine-idle", self.finished_starting_engine)
        self.sound_controller.start_engine()
        
    def perform_engine_shutdown(self):
        self.idle_handler_id = self.sound_controller.connect("engine-idle", self.quit_engine) # quit engine when it is idle!
        GObject.idle_add(self.start_spinner)
        
    def quit_engine(self, sound_controller):
        sound_controller.disconnect(self.idle_handler_id)
        self.stopped_handler_id = self.sound_controller.connect("engine-stopped", self.finished_stopping_engine)
        sound_controller.quit_engine()
        
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
        self.circle_number.queue_draw() # needed for some themes, otherwise the "transparent"-property gets lost and it looks ugly
        
    def stop_spinner(self):
        self.grid.remove(self.spinner)
        self.spinner.stop()
        self.speed_scale.set_sensitive(True)
        self.set_sensitive(True)
        self.circle_number.queue_draw()

class SteamEngineSwitch(EngineSwitch):
    def __init__(self, sound_controller, speed_scale, sound_circle):
        EngineSwitch.__init__(self, sound_controller, speed_scale, sound_circle)
        self.add(self.label)
        
    def set_fill_level(self, loco_speed):
        self.speed_scale.set_fill_level(loco_speed)
        
    def reset_fill_level(self):
        self.speed_scale.set_fill_level(0)
        
    def perform_engine_startup(self):
        self.sound_controller.start_engine()
        
    def perform_engine_shutdown(self):
        self.sound_controller.quit_engine()

class CircleNumber(Gtk.Overlay):
    size = 22
    def __init__(self, nr, circle_pixbuf):
        Gtk.Overlay.__init__(self)
        self.set_transparent()
        circle = Gtk.Image()
        circle.set_from_pixbuf(circle_pixbuf.scale_simple(self.size, self.size, GdkPixbuf.InterpType.BILINEAR))
        self.add(circle)
        nr_label = Gtk.Label()
        nr_label.set_markup("<b>" + str(nr) + "</b>")
        self.add_overlay(nr_label)
        
    def set_transparent(self, *args):
        try:
            self.get_style_context().add_class("transparent")
        except:
            pass

class FunctionButton(Gtk.ToggleButton):
    def __init__(self, function, circle_pixbuf):
        Gtk.ToggleButton.__init__(self)
        self.function = function    # every kind of function-button has the attribute 'function'
                                    # and a unique attribute (e.g. 'function_sound') -> both are the same, 2nd exists for readability
        self.set_size_request(100, 30)
        
        label = Gtk.Label(function.name)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_halign(Gtk.Align.CENTER)
        
        if Config.joystick.show_function_nr and function.button >= 0: # values less than 0 mean there is no func-button
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
    def __init__(self, loco, function, circle_pixbuf, socket):
        FunctionButton.__init__(self, function, circle_pixbuf)
        self.loco = loco
        self.socket = socket
        
    def toggle_function(self, button):
        self.function.toggle()
        self.socket.send(self.loco.get_srcp_status(Config.server.bus))
        locked_print("Funktion", self.function.name, "von Lok", self.loco.name, "hat nun den Status", self.function.state)

class FunctionSoundButton(FunctionButton):
    def __init__(self, function_sound, circle_pixbuf, mixer, channel_id):
        FunctionButton.__init__(self, function_sound, circle_pixbuf)
        self.function_sound = function_sound
        self.mixer = mixer
        self.channel_id = channel_id
        if self.function_sound.toggle_mode == ToggleMode.TAP:
            mixer.add_callback(function_sound.channel_id, self.clicked)
        if self.function_sound.state:
            self.check_queue_sound()
        
    def toggle_function(self, button):
        self.function_sound.toggle()
        self.check_queue_sound()
        
    def check_queue_sound(self):
        if self.function_sound.state:
            self.mixer.queue_sound(self.channel_id, self.function_sound.sound)
            if self.function_sound.toggle_mode in [ToggleMode.SWITCH, ToggleMode.PUSH]:
                self.mixer.queue_sound(self.channel_id, self.function_sound.sound) # queue second time for gapless looping
            elif self.function_sound.toggle_mode == ToggleMode.TAP:
                self.set_sensitive(False)
                self.circle_number.queue_draw() # needed for some themes, otherwise the "transparent"-property gets lost and it looks ugly
        else:
            self.mixer.channels[self.channel_id].stop()
            if self.function_sound.toggle_mode == ToggleMode.TAP:
                self.set_sensitive(True)
                self.circle_number.queue_draw()
        locked_print("Geräusch-Funktion", self.function_sound.name, "hat nun den Status", self.function_sound.state)
        
class EventSoundButton(FunctionButton):
    def __init__(self, event_sound, circle_pixbuf, channel):
        FunctionButton.__init__(self, event_sound, circle_pixbuf)
        self.event_sound = event_sound
        self.channel = channel
        
    def toggle_function(self, button):
        self.event_sound.toggle()
        if not self.event_sound.state:
            self.channel.stop()
        locked_print("Geräusch-Ereignis", self.function.name, "hat nun den Status", self.function.state)
            
class FunctionBox(Gtk.Grid):
    def __init__(self, loco, speed_scale, event_thread, socket, circle_pixbufs):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_halign(Gtk.Align.CENTER)
        self.buttons = [LocoFunctionButton(loco, function, circle_pixbufs["loco_function"], socket) for function in loco.functions]
        self.boxes = []
        self.nr_rows = 0
        
        func_nr = 0 # we need func-nr in the whole method, therefore it must be declared here
        if loco.function_sounds != None:
            FunctionSoundController(event_thread,
                                    loco.function_sounds,
                                    loco.sound_volume) # add the needed 'sound' and 'channel_id' attribs to the func-sound-objs
            for func_nr, function_sound in enumerate(loco.function_sounds):
                self.buttons.insert(func_nr, FunctionSoundButton(function_sound,
                                                                 circle_pixbufs["function_sound"],
                                                                 event_thread,
                                                                 function_sound.channel_id))
        
        if loco.engine != None:
            self.sound_switch = create_engine_switch(loco.engine.type, loco.sound_controller, speed_scale, circle_pixbufs["speed_sound"])
            for ev_nr, event_sound in enumerate(loco.engine.event_sounds):
                self.buttons.insert(ev_nr + func_nr + 1, EventSoundButton(event_sound,
                                                                          circle_pixbufs["event_sound"],
                                                                          event_thread.channels[event_sound.channel_id]))
            self.buttons.insert(0, self.sound_switch)
            
        nr_buttons = len(self.buttons)

        if nr_buttons > 0:            
            nr_columns, rest_columns = divmod(nr_buttons, 5) # estimate the number of columns needed
            if rest_columns > 0:
                nr_columns += 1
                
            buttons_per_column, rest_buttons = divmod(nr_buttons, nr_columns) # estimate the nr of buttons per box if the buttons are equally spread
            if rest_buttons > 0:
                buttons_per_column += 1
                
            nr_buttons_left = nr_buttons
            for col_nr in xrange(nr_columns):
                box = FunctionButtonBox()
                
                if nr_buttons_left > buttons_per_column:
                    nr_buttons_to_pack = buttons_per_column
                else:
                    nr_buttons_to_pack = nr_buttons_left
                
                for row in xrange(nr_buttons_to_pack):
                    box.pack_start(self.buttons[nr_buttons - nr_buttons_left + row], True, True, 0)
                
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
#        context = self.get_style_context()
#        context.add_class(Gtk.STYLE_CLASS_LINKED) # TODO: uncomment when gtk-themes can do that in future (make the boxes appear as one nice unit)
        self.set_homogeneous(True)

class EmergencyButton(Gtk.ToggleButton):
    def __init__(self, socket):
        Gtk.ToggleButton.__init__(self)
        self.set_name("emergency-button")
        
        self.set_label("Nothalt")
        self.set_size_request(-1 , 50)
        self.socket = socket
        
        if not Config.server.power:
            self.set_active(True)
        self.send_power()
            
        self.connect("clicked", self.toggle_power)
    
    def toggle_power(self, *args):
        Config.server.toggle_power()
        self.send_power()
        
    def send_power(self):
        if Config.server.power:
            self.socket.send("SET 1 POWER ON\n")
            locked_print("\nStrom angeschaltet")
        else:
            self.socket.send("SET 1 POWER OFF\n")
            locked_print("\nNotstop eingeleitet")
