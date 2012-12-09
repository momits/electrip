#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository.GLib import GError
from gi.repository import GObject, Gtk, Pango, GdkPixbuf
import socket
from LockedPrint import locked_print, SocketRecvThread
from Pygame import JoystickAndSound

class MainBox(Gtk.Grid):    
    def __init__(self, config_copy, main_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        global Config
        Config = config_copy
        Config.notice_unsaved_changes = False
        self.main_window = main_window
        try:
            self.socket_init()
        except socket.error:
            self.main_window.error("Es konnte keine Verbindung zum SRCP-Server aufgebaut werden.\nÜberprüfen Sie die Server-Einstellungen (Host, Port ...).\nIst der SRCP-Server aktiv?")
            self.main_window.basic_vbox.top_grid.config_control_switch.config_button.set_active(True)
        else:
            self.event_thread = JoystickAndSound.EventHandlerThread(Config)
            self.scrolled_window = ScrolledWindow(self.socket, self) # ScrolledWindow und darin HBox für Controller erzeugen
            self.emergency_button = EmergencyButton(self.socket) # HBox für Notstop erzeugen
            self.add(self.scrolled_window)
            self.add(self.emergency_button)
            
            try:
                self.event_thread.joystick_init(self.scrolled_window.center_hbox.controllers, self.emergency_button)
                self.event_thread.start()
            except NameError:
                locked_print("Konnte pygame-PygameThreads nicht starten, Joysticks werden folglich nicht erkannt.")
            self.show_all()
    
    def quit(self):
        self.event_thread.quit()
        self.socket.send("TERM 1 POWER\n")
        self.socket.send("TERM 0 SESSION\n")
        self.socket_thread.quit()
        locked_print("Steuerung geschlossen.")
        self.destroy()
    
    def socket_init(self):
        bus = str(Config.server.loco_bus)
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
            loco.send_to_server(Config.server.loco_bus, self.socket);
            locked_print(self.socket.recv(4096))

        self.socket_thread = SocketRecvThread(self.socket) # Nach dem Handshake und Loco-Init wird der Receive in einen separaten Thread verlegt -> keine MainWindow-Blockierungen möglich
        self.socket_thread.start()
        
class ScrolledWindow(Gtk.ScrolledWindow):
    def __init__(self, socket, main_window):
        Gtk.ScrolledWindow.__init__(self)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.center_hbox = CenterGrid(socket, main_window, self)
        self.add_with_viewport(self.center_hbox)
        
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
        self.connect("realize", self.realized, main_window)
                
    def realized(self, hbox, control_window):        
        max_height = 0
        max_label_width = 0
        config_has_functions = False
        for controller in self.controllers:
            controller.function_box = FunctionBox(controller.loco, self.socket)
            controller.function_box.show_all()
            controller.add(controller.function_box)
            height = controller.function_box.get_preferred_height()[1]
            if height > max_height:
                max_height = height
            if not config_has_functions and len(controller.function_box.buttons) > 0:
                config_has_functions = True
            width = controller.loco_label.get_preferred_width()[1]
            if width > max_label_width :
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
        if loco.use_sound:
            sound_controller = JoystickAndSound.SoundController(event_thread, loco)
        else:
            sound_controller = None
        self.speed_scale = SpeedScale(loco, socket, sound_controller)
        self.loco_label = LocoLabel(loco)
        self.reverser = Reverser(loco, socket, self.speed_scale)
        self.gamepad_image = Gtk.Image()
        self.gamepad_image.set_size_request(110, 50)
        self.scrolled_window = scrolled_window
        
        self.add(self.loco_image)
        self.add(self.speed_scale)
        self.add(Gtk.Label.new("km/h"))
        self.add(self.loco_label)
        self.add(self.gamepad_image)
        self.add(self.reverser)
        if loco.use_sound:
            self.sound_switch = SoundEngineSwitch(sound_controller, self.speed_scale)
            self.add(self.sound_switch)
        
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
                small_pixbuf = pixbuf.scale_simple(110 , 85, GdkPixbuf.InterpType.BILINEAR)
                self.set_from_pixbuf(small_pixbuf)
            except GError:
                self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
                locked_print("Dateipfad '" + path + "' für Lokbild ist ungültig.")

class SpeedScale(Gtk.Scale):
    def __init__(self, loco, socket, sound_controller=None):
        Gtk.Scale.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.set_adjustment(Gtk.Adjustment(0, 0, loco.max_speed, 0.01, 0, 0))
        self.connect("value-changed", self.speed_changed, loco, socket, sound_controller)
        self.set_inverted(True)
        self.set_digits(1)
        self.set_value_pos(Gtk.PositionType.BOTTOM)

    def speed_changed(self, scale, loco, socket, sound_controller):
        loco.speed = self.get_value()
        speed_step = loco.speed_to_step_func.get_y(loco.speed)
        if speed_step != None:
            loco.speed_step = speed_step
        if int(loco.speed_step) != loco.last_speed_step:
            loco.send_to_server(Config.server.loco_bus, socket)
        if sound_controller != None and sound_controller.engine_is_running:
            sound_controller.set_scheduled_speed(loco.speed)
        locked_print("Lok", loco.name, "fährt jetzt", loco.speed, "km/h, das entspricht", int(loco.speed_step), "Fahrstufen.")

class LocoLabel(Gtk.Label):
    def __init__(self, loco):
        self.text = loco.name
        Gtk.Label.__init__(self, self.text)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_max_width_chars(20)
        self.set_margin_top(7)
    
    def set_bold(self, is_bold):
        if is_bold:
            self.set_markup("<b>" + self.text + "</b>")
        else:
            self.set_markup(self.text)

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
            self.loco.send_to_server(Config.server.loco_bus, socket)
        else:
            scale.set_value(0)
        self.set_arrow()
        locked_print("\nLok", self.loco.name, "hat die Richtung gewechselt und fährt nun", self.loco.direction)
    
    def set_arrow(self):
        if self.loco.direction:
            self.set_image(self.arrow_up)
        else:
            self.set_image(self.arrow_down)

class SoundEngineSwitch(Gtk.ToggleButton):
    def __init__(self, sound_controller, speed_scale):
        Gtk.ToggleButton.__init__(self)
        self.label = Gtk.Label("Geräusch")
        self.label.set_hexpand(True)
        
        self.grid = Gtk.Grid()
        self.grid.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.grid.set_column_spacing(5)
        self.grid.add(self.label)
        self.add(self.grid)
        
        self.spinner = Gtk.Spinner()
        self.spinner.show()
        
        self.set_active(False)
        self.connect("notify::active", self.engine_toggled)
        self.sound_controller = sound_controller
        self.speed_scale = speed_scale
        
    def engine_toggled(self, switch, is_active):
        loco_speed = self.speed_scale.get_value()
        if self.get_active() and not self.sound_controller.engine_is_running:
            if loco_speed == 0:
                self.start_spinner()
                self.sound_controller.start_engine()
                self.idle_handler_id = self.sound_controller.connect("engine-idle", self.finished_starting_engine)
            else:
                self.sound_controller.start_engine_with_speed(loco_speed)
            
        elif not switch.get_active() and self.sound_controller.engine_is_running:
            if loco_speed == 0:
                GObject.idle_add(self.start_spinner)
                self.idle_handler_id = self.sound_controller.connect("engine-idle", self.quit_engine) # quit engine when it is idle! otherwise error
            else:
                self.sound_controller.pause_engine()
                
    def quit_engine(self, sound_controller):
        sound_controller.disconnect(self.idle_handler_id)
        sound_controller.quit_engine()
        self.stopped_handler_id = self.sound_controller.connect("engine-stopped", self.finished_stopping_engine)
        
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
        
    def stop_spinner(self):
        self.grid.remove(self.spinner)
        self.spinner.stop()
        self.speed_scale.set_sensitive(True)
        self.set_sensitive(True)

class FunctionToggleButton(Gtk.ToggleButton):
    def __init__(self, loco, function, socket):
        Gtk.ToggleButton.__init__(self)
        self.loco = loco
        self.socket = socket
        
        self.child_label = Gtk.Label()
        self.child_label.set_ellipsize(Pango.EllipsizeMode.END)
        
        if Config.joystick.show_function_nr:
            self.child_label.set_markup("<b>" + str(function.button) + "</b> - " + function.name)
        else:
            self.child_label.set_text(function.name)
        self.add(self.child_label)
        self.function = function
        
        if function.state:
            self.set_active(True)
        self.connect("clicked", self.toggle_function)
        
    def toggle_function(self, button):
        self.function.toggle()
        self.loco.send_to_server(Config.server.loco_bus, self.socket)
        locked_print("Funktion", self.function.name, "von Lok", self.loco.name, "hat nun den Status", self.function.state)
            
class FunctionBox(Gtk.Grid):
    def __init__(self, loco, socket):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_halign(Gtk.Align.CENTER)
        self.buttons = [FunctionToggleButton(loco, function, socket) for function in loco.functions]
        self.boxes = []
        self.nr_rows = 0

        if len(loco.functions) > 0:            
            nr_columns, rest_columns = divmod(len(loco.functions), 5) # estimate the number of columns needed
            if rest_columns > 0:
                nr_columns += 1
                
            buttons_per_column, rest_buttons = divmod(len(loco.functions), nr_columns) # estimate the nr of buttons per box if the buttons are equally spread
            if rest_buttons > 0:
                buttons_per_column += 1
                
            nr_buttons_left = len(loco.functions)
            for col_nr in xrange(nr_columns):
                box = FunctionButtonBox()
                
                if nr_buttons_left > buttons_per_column:
                    nr_buttons_to_pack = buttons_per_column
                else:
                    nr_buttons_to_pack = nr_buttons_left
                
                for row in xrange(nr_buttons_to_pack):
                    box.pack_start(self.buttons[len(loco.functions) - nr_buttons_left + row], True, True, 0)
                
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
        #context = self.get_style_context()
        #context.add_class(Gtk.STYLE_CLASS_LINKED) # TODO: uncomment when gtk can do that in future (make the boxes appear as one nice unit)
        self.set_homogeneous(True)

class EmergencyButton(Gtk.ToggleButton):
    def __init__(self, socket):
        Gtk.ToggleButton.__init__(self)
        self.set_name("emergency-button")
        
        self.set_label("Nothalt")
        self.set_size_request(-1 , 60)
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
