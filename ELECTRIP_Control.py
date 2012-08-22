#!/usr/bin/env python
# -*- coding: utf-8 -*-
# this is ELECTRIP VERSION 2.1.6

from gi.repository.GLib import GError
from gi.repository import Gtk, Pango, GdkPixbuf
import socket
import Joystick.JoystickConsole as joystick_console
from LockedPrint import locked_print, SocketRecvThread

class MainBox(Gtk.Box):
    def __init__(self, config_copy, main_window):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        global Config
        Config = config_copy
        Config.notice_unsaved_changes = False
        self.main_window = main_window
        try:
            self.socket_init()
            self.scrolled_window = ScrolledWindow(self.socket, self) # ScrolledWindow und darin HBox für Controller erzeugen
            self.emergency_button = EmergencyButton(self.socket) # HBox für Notstop erzeugen
            self.top_hbox = Gtk.Box()
            self.top_hbox.set_orientation(Gtk.Orientation.HORIZONTAL)
            self.pack_start(self.scrolled_window, True, True, 0)
            self.pack_start(self.emergency_button, False, False, 0)
            try: 
                self.joystick_konsole = joystick_console.JoystickConsole(Config, self.scrolled_window.center_hbox.controller, self.emergency_button)
            except NameError:
                locked_print("Konnte pygame-Threads nicht starten, Joysticks werden folglich nicht erkannt.")
            self.show_all()
        except socket.error:
            self.main_window.error("Es konnte keine Verbindung zum SRCP-Server aufgebaut werden.\nÜberprüfen Sie die Server-Einstellungen (Host, Port ...).\nIst der SRCP-Server am Laufen?")
            self.main_window.basic_vbox.buttonbox_top.config_control_switch.config_button.set_active(True)
    
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
        # Socket-Verbindung herstellen
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
        
        # -------- Stromversorgung auf Bus 1 initiieren ---------
        locked_print("Strom wird angeschaltet")
        self.socket.send("INIT " + server_bus + " POWER\n")
        locked_print(self.socket.recv(4096))
        
        # ---------- locos initialisieren -------------
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

class FullscreenButton(Gtk.ToggleButton):
    def __init__(self, control_window):
        Gtk.ToggleButton.__init__(self)
        icon = Gtk.Image()
        icon.set_from_stock(Gtk.STOCK_FULLSCREEN, Gtk.IconSize.BUTTON)
        label = Gtk.Label(label="Vollbild")
        hbox = Gtk.Box(False, 5)
        hbox.set_orientation(Gtk.Orientation.HORIZONTAL)
        hbox.pack_start(label, True, True, 0)
        hbox.pack_start(icon, True, True, 0)
        self.add(hbox)
        self.set_size_request(-1, 30)
        self.connect("clicked", self.clicked, control_window)
    
    def clicked(self, button, control_window):
        if control_window.is_fullscreen:
            self.toggled()
            control_window.unfullscreen()
            control_window.is_fullscreen = False
        else:
            self.toggled()
            control_window.fullscreen()
            control_window.is_fullscreen = True
        
class ScrolledWindow(Gtk.ScrolledWindow):
    def __init__(self, socket, main_window):
        Gtk.ScrolledWindow.__init__(self)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.center_hbox = CenterHBox(socket, main_window, self)
        self.add_with_viewport(self.center_hbox)
        
class CenterHBox(Gtk.Box):
    def __init__(self, socket, main_window, scrolled_window):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_homogeneous(True)
        self.controller = []
        self.socket = socket
        for i in range(len(Config.locos)): # Alle Controller hinzufügen
            self.controller.append(Controller(socket, Config.locos[i], scrolled_window))
            self.pack_start(self.controller[i], True, True, 0)
        self.connect("realize", self.realized, main_window)
                
    def realized(self, hbox, control_window):
        min_req, natural_req = self.get_preferred_size()
        #control_window.resize(natural_req.width + 100, natural_req.height + 100)
        
        max_nr_buttons_per_box = 0
        search_pending = True # Suche nach einem Funktionsbutton um Höhe zu ermitteln
        for controller in self.controller:
            controller.hbox = FunctionVBox(controller.loco, self.socket)
            controller.hbox.show_all()
            controller.pack_start(controller.hbox, False, False, 10)
            if controller.hbox.max_nr_buttons > max_nr_buttons_per_box: # finde spalte mit den meisten buttons (mit der bedingung geht einher, dass controller.hbox mindestens einen Funktionsbutton besitzt)
                max_nr_buttons_per_box = controller.hbox.max_nr_buttons
                if search_pending:
                    button_req = controller.hbox.buttons[0].get_preferred_size()[1]
                    search_pending = False
        
        if max_nr_buttons_per_box > 0:
            for controller in self.controller:
                if len(controller.hbox.boxes) > 0:    
                    for box in controller.hbox.boxes:
                        box.set_size_request(-1, button_req.height * max_nr_buttons_per_box)
                else:
                    controller.hbox.set_size_request(-1, button_req.height * max_nr_buttons_per_box)

class Controller(Gtk.Box):
    def __init__(self, socket, loco, scrolled_window):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.loco = loco
        self.joystick = None
        self.loco_image = LocoImage(loco.img_path)
        self.speed_scale = SpeedScale(loco, socket)
        self.loco_label = LocoLabel(loco)
        self.reverser = Reverser(loco, socket, self.speed_scale)
        self.gamepad_image = Gtk.Image()
        self.gamepad_image.set_size_request(110, 50)
        self.scrolled_window = scrolled_window
        
        self.pack_start(self.loco_image, False, False, 0)
        self.pack_start(self.speed_scale, True, True, 0)
        self.pack_start(self.loco_label, False, False, 0)
        self.pack_start(self.gamepad_image, False, False, 0)
        self.pack_start(self.reverser, False, False, 0)
        
    def set_focus(self): # Controller im ScrolledWindow sichtbar machen
        adjust = self.scrolled_window.get_hadjustment()
        allocation = self.get_allocation()
        adjust.clamp_page(allocation.x, allocation.x + allocation.width)
    
class LocoImage(Gtk.Image):
    def __init__(self, pfad):
        Gtk.Image.__init__(self)
        self.set_size_request(110, 85)
        if pfad == None:
            self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
        else:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(pfad)
                small_pixbuf = pixbuf.scale_simple(110 , 85, GdkPixbuf.InterpType.BILINEAR)
                self.set_from_pixbuf(small_pixbuf)
            except GError:
                self.set_from_stock(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.BUTTON)
                locked_print("Dateipfad '" + pfad + "' für Lokbild ist ungültig.")

class SpeedScale(Gtk.Scale):
    def __init__(self, loco, socket):
        Gtk.Scale.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_adjustment(Gtk.Adjustment(0, 0, loco.v_max, 0.01, 0, 0))
        self.connect("value-changed", self.speed_changed, loco, socket)
        self.set_inverted(True)
        self.set_digits(1)
        self.set_value_pos(Gtk.PositionType.BOTTOM)

    def speed_changed(self, scale, loco, socket):
        loco.deviation = self.get_value()
        speed = loco.deviation_speed_func.get_y(loco.deviation)
        locked_print("Speed:", speed)
        if speed != None:
            loco.speed = speed
        if int(loco.speed) != loco.last_speed:
            loco.send_to_server(Config.server.loco_bus, socket)
        #locked_print("Loco", loco.name, "fährt jetzt", loco.speed, ", das entspricht", int(loco.speed), "Fahrstufen.")

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
        if self.loco.speed == 0:
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
            
class FunctionVBox(Gtk.Box):
    def __init__(self, loco, socket):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.boxes = []
        self.max_nr_buttons = 0
        
        self.buttons = [FunctionButton(loco, function, socket) for function in loco.functions]

        if len(loco.functions) > 0:            
            nr_boxes, rest_boxes = divmod(len(loco.functions), 5) # ermittle, wie viele boxes erzeugt werden müssen
            if rest_boxes > 0:
                nr_boxes += 1
            buttons_per_box, rest_buttons = divmod(len(loco.functions), nr_boxes) # ermittle, wie viele buttons in eine box kommen, wenn sie gleichmäßig verteilt werden sollen
            
            nr_buttons = len(loco.functions)
            
            for box_nr in range(int(nr_boxes)):
                box = Gtk.ButtonBox()
                box.set_orientation(Gtk.Orientation.VERTICAL)
                box.set_layout(Gtk.ButtonBoxStyle.START)
                
                if nr_buttons > buttons_per_box:
                    nr_buttons_to_pack = buttons_per_box
                else:
                    nr_buttons_to_pack = nr_buttons
                
                if rest_buttons > 0:
                    nr_buttons_to_pack += 1
                    rest_buttons -= 1
                
                for i in range(nr_buttons_to_pack):
                    box.pack_start(self.buttons[len(loco.functions) - nr_buttons + i], True, True, 0)
                
                nr_buttons -= nr_buttons_to_pack
                
                if nr_buttons_to_pack > self.max_nr_buttons:
                    self.max_nr_buttons = nr_buttons_to_pack
                    
                self.boxes.append(box)
                self.pack_start(box, True, True, 0)

class EmergencyButton(Gtk.ToggleButton):
    def __init__(self, socket):
        Gtk.ToggleButton.__init__(self)
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
