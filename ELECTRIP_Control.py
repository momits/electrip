#!/usr/bin/env python
# -*- coding: utf-8 -*-
# this is ELECTRIP VERSION 2.1.6

from gi.repository.GLib import GError
from gi.repository import Gdk, Gtk, Pango, GdkPixbuf
import socket
import Joystick.JoystickConsole as joystick_console
from LockedPrint import locked_print, SocketRecvThread

class MainBox(Gtk.Grid):
    def __init__(self, config_copy, main_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_row_spacing(10)
        global Config
        Config = config_copy
        Config.notice_unsaved_changes = False
        self.main_window = main_window
        try:
            self.socket_init()
            self.scrolled_window = ScrolledWindow(self.socket, self) # ScrolledWindow und darin HBox für Controller erzeugen
            self.emergency_button = EmergencyButton(self.socket) # HBox für Notstop erzeugen
            self.add(self.scrolled_window)
            self.add(self.emergency_button)
            try: 
                self.joystick_konsole = joystick_console.JoystickConsole(Config, self.scrolled_window.center_hbox.controllers, self.emergency_button)
            except NameError:
                locked_print("Konnte pygame-Threads nicht starten, Joysticks werden folglich nicht erkannt.")
            self.show_all()
        except socket.error:
            self.main_window.error("Es konnte keine Verbindung zum SRCP-Server aufgebaut werden.\nÜberprüfen Sie die Server-Einstellungen (Host, Port ...).\nIst der SRCP-Server am Laufen?")
            self.main_window.basic_vbox.top_grid.config_control_switch.config_button.set_active(True)
    
    def quit(self):
        try:
            self.joystick_konsole.quit()
            self.socket_thread.quit()
            self.socket.send("TERM 1 POWER\n")
            self.socket.send("TERM 0 SESSION\n")
        except:
            pass
        self.destroy()
        locked_print("Steuerung geschlossen.")
    
    def socket_init(self):
        server_bus = str(Config.server.loco_bus)
        # Create Socket-Connection
        self.socket = socket.create_connection((Config.server.host, Config.server.port))
        #-------- Handshake ----------
        locked_print("Socketverbindung aktiv mit:")
        locked_print(self.socket.recv(4096))
        self.socket.send("SET CONNECTIONMODE SRCP COMMAND\n")
        locked_print("Connectionmode 'Command' wird angefordert:")
        locked_print(self.socket.recv(4096))
        self.socket.send('GO\n')
        
        locked_print("Von ELECTRIP aus kanns losgehen, was sagt der Server?")
        locked_print(self.socket.recv(4096))
        
        # -------- Initialize Power on Server-Bus ---------
        locked_print("Strom wird angeschaltet")
        self.socket.send("INIT " + server_bus + " POWER\n")
        locked_print(self.socket.recv(4096))
        
        # ---------- Initialize Locos -------------
        for loco in Config.locos:
            if len(loco.functions) > 0:
                nr_functions_to_send = max(function.nr for function in loco.functions)
            else:
                nr_functions_to_send = 0
            text = "INIT " + server_bus + " GL " + str(loco.address) + " " + str(loco.protocol) + " " + str(int(loco.speed_steps)) + " " + str(nr_functions_to_send) + "\n"
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
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.center_hbox = CenterGrid(socket, main_window, self)
        self.add_with_viewport(self.center_hbox)
        
class CenterGrid(Gtk.Grid):
    def __init__(self, socket, main_window, scrolled_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_column_spacing(8)
        self.controllers = []
        self.socket = socket
        for i in range(len(Config.locos)): # Alle Controller hinzufügen
            self.controllers.append(Controller(socket, Config.locos[i], scrolled_window))
            self.add(self.controllers[i])
        self.connect("realize", self.realized, main_window)
                
    def realized(self, hbox, control_window):
        min_req, natural_req = self.get_preferred_size()
        
        max_nr_rows = 0
        search_pending = True # Suche nach einem Funktionsbutton um Höhe zu ermitteln
        for controller in self.controllers:
            controller.hbox = FunctionVBox(controller.loco, self.socket)
            controller.hbox.show_all()
            controller.add(controller.hbox)
            if controller.hbox.nr_rows > max_nr_rows: # finde spalte mit den meisten buttons (mit der bedingung geht einher, dass controller.hbox mindestens einen Funktionsbutton besitzt)
                max_nr_rows = controller.hbox.nr_rows
                if search_pending:
                    button_req = controller.hbox.buttons[0].get_preferred_size()[1]
                    search_pending = False
        locked_print("max nr rows:", max_nr_rows)
        height = button_req.height * max_nr_rows
        if max_nr_rows > 0:
            for controller in self.controllers:
                controller.hbox.set_size_request(-1, height)

class Controller(Gtk.Grid):
    def __init__(self, socket, loco, scrolled_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(True)
        self.loco = loco
        self.joystick = None
        self.loco_image = LocoImage(loco.img_path)
        self.speed_scale = SpeedScale(loco, socket)
        self.loco_label = LocoLabel(loco)
        self.reverser = Reverser(loco, socket, self.speed_scale)
        self.gamepad_image = Gtk.Image()
        self.gamepad_image.set_size_request(110, 50)
        self.scrolled_window = scrolled_window
        
        self.add(self.loco_image)
        self.add(self.speed_scale)
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
                small_pixbuf = pixbuf.scale_simple(110 , 85, GdkPixbuf.InterpType.BILINEAR)
                self.set_from_pixbuf(small_pixbuf)
            except GError:
                self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
                locked_print("Dateipfad '" + path + "' für Lokbild ist ungültig.")

class SpeedScale(Gtk.Scale):
    def __init__(self, loco, socket):
        Gtk.Scale.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.set_adjustment(Gtk.Adjustment(0, 0, loco.max_speed, 0.01, 0, 0))
        self.connect("value-changed", self.speed_changed, loco, socket)
        self.set_inverted(True)
        self.set_digits(1)
        self.set_value_pos(Gtk.PositionType.BOTTOM)

    def speed_changed(self, scale, loco, socket):
        loco.speed = self.get_value()
        speed_step = loco.speed_to_step_func.get_y(loco.speed)
        if speed_step != None:
            loco.speed_step = speed_step
        if int(loco.speed_step) != loco.last_speed_step:
            loco.send_to_server(Config.server.loco_bus, socket)
        locked_print("Loco", loco.name, "fährt jetzt", loco.speed_step, ", das entspricht", int(loco.speed_step), "Fahrstufen.")

class LocoLabel(Gtk.Label):
    def __init__(self, loco):
        self.text = loco.name
        Gtk.Label.__init__(self, self.text)
        self.set_ellipsize(Pango.EllipsizeMode.END)
    
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

    def toggle_direction(self, button, socket, scale):
        self.loco.toggle_direction()
        if self.loco.speed_step == 0: # if direction has changed but speed is already 0
            self.loco.send_to_server(Config.server.loco_bus, socket)
        else:
            scale.set_value(0)
        self.set_arrow()
        locked_print("\nloco", self.loco.name, "hat die Richtung gewechselt und fährt nun", self.loco.direction)
    
    def set_arrow(self):
        if self.loco.direction:
            self.set_image(self.arrow_up)
        else:
            self.set_image(self.arrow_down)

class FunctionButton(Gtk.ToggleButton):
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
        self.toggled()
        locked_print("Funktion", self.function.name, "von Lok", self.loco.name, "hat nun den Status", self.function.state)
            
class FunctionVBox(Gtk.Grid):
    def __init__(self, loco, socket):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_halign(Gtk.Align.CENTER)
        self.buttons = [FunctionButton(loco, function, socket) for function in loco.functions]
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
        self.connect("clicked", self.toggle_power)
        
        if not Config.server.power:
            self.set_active(True)
    
    def toggle_power(self, *args):
        Config.server.toggle_power()
        if Config.server.power:
            self.socket.send("SET 1 POWER ON\n")
            locked_print("\nStrom angeschaltet")
        else:
            self.socket.send("SET 1 POWER OFF\n")
            locked_print("\nNotstop eingeleitet")
        self.toggled()
