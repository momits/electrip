#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import getcwd, path as os_path
package_path = os_path.dirname(getcwd()) # find parent-directory of current working-directory
from sys import path, argv
path.append(package_path) # add path to sys.path, to allow relative imports in submodules

from gi.repository import GObject, Gtk, GdkPixbuf, Gdk
import config
from Constants import ELECTRIP_VERSION, ICON_PATHS
import Configuration
import DialogUtilities
import Control
from LockedPrint import locked_print
from socket import error as SocketError
import gc

class MainWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_title("Electrip " + ELECTRIP_VERSION)
        icon_list = [GdkPixbuf.Pixbuf.new_from_file(path) for path in ICON_PATHS]
        self.set_icon_list(icon_list)
        self.connect("delete-event", self.quit)
        
        self.basic_vbox = BasicVBox(self)
        self.add(self.basic_vbox)
        
        if len(argv) > 2 and (argv[1] == "-f" or argv[1] == "--file"):
            file_path = argv[2]
            success = self.basic_vbox.top_grid.load_button.load(file_path, self)
            if success:
                self.basic_vbox.top_grid.config_control_switch.control_button.set_active(True)
        
        Config.notice_unsaved_changes = True # this  can't be set earlier, because loading process would cause unsaved changes
        self.maximize()
        self.show_all()
        
    def quit(self, window, event):
        response = 1
        if Config.has_unsaved_changes:
            dialog = Gtk.MessageDialog(self,
                                       0,
                                       Gtk.MessageType.QUESTION,
                                       Gtk.ButtonsType.NONE,
                                       "Die Datei besitzt ungespeicherte Änderungen.\n Wollen Sie diese speichern?")
            dialog.add_buttons("Speichern", 0, "Verwerfen und Electrip beenden", 1, "Abbrechen", 2)
            response = dialog.run()
            dialog.destroy()
            if response == 0 and Config.opened_file == None:
                self.basic_vbox.top_grid.save_as_button.save(None, self)
            elif response == 0:
                Config.save(Config.last_file)
        if response != 2:
            if self.basic_vbox.top_grid.config_control_switch.control_button.get_active():
                self.basic_vbox.control_box.quit()
            Gtk.main_quit()
            locked_print("Electrip wurde beendet.")
        else:
            dialog.destroy()
            return True
    
    def error_dialog(self, warning):
        error_dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, warning)
        error_dialog.run()
        error_dialog.destroy()

class BasicVBox(Gtk.Grid):
    def __init__(self, main_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        
        self.config_box = Configuration.MainBox(Config, main_window)
        self.top_grid = TopGrid(self.config_box.loco_scrolled_window.treeview,
                                          self.config_box.loco_properties_frame.table,
                                          self.config_box.function_frame.treeview,
                                          self.config_box.server_table,
                                          self.config_box.joystick_table,
                                          self.config_box.sound_table,
                                          main_window)
        try:
            screen = Gdk.Screen.get_default()
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path("gtk_styles_and_transitions.css")
            context = Gtk.StyleContext()
            context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        except: # we dont really NEED special themeing, it shouldnt break anything if it doesn't work
            pass
        self.add(self.top_grid)
        self.add(self.config_box)

class StockImageButton(Gtk.Button):
    def __init__(self, label, stock):
        Gtk.Button.__init__(self)
        icon = Gtk.Image()
        icon.set_from_stock(stock, Gtk.IconSize.BUTTON)
        grid = Gtk.Grid()
        grid.set_orientation(Gtk.Orientation.HORIZONTAL)
        grid.set_column_spacing(5)
        if label != None:
            label = Gtk.Label(label)
            label.set_hexpand(True)
            grid.add(label)
        grid.add(icon)
        self.add(grid)

class LoadButton(StockImageButton):
    loading = False
    def __init__(self,
                 loco_treeview,
                 loco_property_table,
                 function_treeview,
                 server_table,
                 joystick_table,
                 sound_table,
                 main_window):
        StockImageButton.__init__(self, "Laden", Gtk.STOCK_OPEN)
        self.loco_treeview = loco_treeview
        self.function_treeview = function_treeview
        self.loco_property_table = loco_property_table
        self.server_table = server_table
        self.joystick_table = joystick_table
        self.sound_table = sound_table
        self.connect("clicked", self.load_dialog, main_window)
        
    def load_dialog(self, button, main_window):
        if not self.loading:
            self.loading = True
            file_chooser_dialog = DialogUtilities.FileLoadDialog(main_window)
            file_chooser_dialog.set_filename(Config.last_file)
            response = file_chooser_dialog.run()
            if response == Gtk.ResponseType.OK:
                path = file_chooser_dialog.get_filename()
                self.load(path, main_window)
                main_window.show_all()
            elif response == Gtk.ResponseType.CANCEL:
                locked_print("Laden abgebrochen.")
            file_chooser_dialog.destroy()
            self.loading = False
        
    def load(self, path, main_window):
        try:
            Config.load(path)
        except ValueError:
            main_window.error_dialog("Die Datei ist ungültig! Konnte Konfiguration nicht laden.")
            return False
        except IOError:
            main_window.error_dialog("Der Dateipfad ist ungültig! Konnte Konfiguration nicht laden.")
            return False
        except KeyError:
            main_window.error_dialog("Ein Parameter konnte nicht geladen werden, evtl. handelt es ich um eine veraltete Electrip-Datei.")
            return False
        else:
            self.loco_treeview.load()
            self.joystick_table.load(Config.joystick)
            self.server_table.load(Config.server)
            self.sound_table.load(Config.sound)
            if main_window.basic_vbox.top_grid.config_control_switch.control_button.get_active(): # if control is active
                if hasattr(Config, "new_unsaved_changes_method"):
                    del Config.new_unsaved_changes_method
                main_window.basic_vbox.control_box.quit()
                main_window.basic_vbox.control_box = Control.MainBox(Config, main_window) # deepcopy the Config so that it isn't messed up by Control
                main_window.basic_vbox.add(main_window.basic_vbox.control_box)

            main_window.set_title("Electrip " + ELECTRIP_VERSION + " - " + path)
            return True
            
class SaveAsButton(StockImageButton):
    def __init__(self, main_window):
        StockImageButton.__init__(self, "Speichern unter", Gtk.STOCK_SAVE_AS)
        self.connect("clicked", self.save, main_window)
        
    def save(self, button, main_window):
        file_chooser_dialog = DialogUtilities.FileSaveDialog(main_window)
        file_chooser_dialog.set_filename(Config.last_file)
        response = file_chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            path = file_chooser_dialog.get_filename()
            if path != "" and path[len(path) - 5:len(path)] != ".json": # if a file-name was chosen but ending is missing, add ending
                path += ".json"
            Config.save(path)
            main_window.set_title("Electrip " + ELECTRIP_VERSION + " - " + path)
        file_chooser_dialog.destroy()

class SaveButton(StockImageButton):
    def __init__(self, main_window):
        StockImageButton.__init__(self, "Speichern", Gtk.STOCK_SAVE)
        self.connect("clicked", self.save, main_window)
        self.set_sensitive(False)
        Config.new_unsaved_changes_method = self.new_unsaved_changes
        
    def save(self, button, config_window):
        Config.save(Config.last_file)
        self.set_sensitive(False)
        
    def new_unsaved_changes(self):
        self.set_sensitive(True)

class ConfigControlSwitch(Gtk.ButtonBox):
    def __init__(self, main_window):
        Gtk.ButtonBox.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_layout(Gtk.ButtonBoxStyle.CENTER)
        
        self.config_button = Gtk.RadioButton.new_with_label_from_widget(None, "Konfiguration")
        self.pack_start(self.config_button, True, True, 0)
        
        self.control_button = Gtk.RadioButton.new_with_label_from_widget(self.config_button, "Steuerung")
        self.control_button.connect("toggled", self.control_toggled, main_window)
        self.pack_start(self.control_button, True, True, 0)
    
    def control_toggled(self, button, main_window):
        if button.get_active():
            main_window.basic_vbox.remove(main_window.basic_vbox.config_box)
            try:
                main_window.basic_vbox.control_box = Control.MainBox(Config, main_window)
            except SocketError:
                main_window.error_dialog("Es konnte keine Verbindung zum SRCP-Server aufgebaut werden.\n" + 
                                         "Überprüfen Sie die Server-Einstellungen (Host, Port ...).\nIst der SRCP-Server aktiv?")
                self.config_button.set_active(True)
            else:
                main_window.basic_vbox.add(main_window.basic_vbox.control_box)
        else:
            if hasattr(main_window.basic_vbox, "control_box"): 
                main_window.basic_vbox.control_box.quit()
                del main_window.basic_vbox.control_box
            
            # Collect the objects which have been freed in the "quit"-methods
            gc.collect()
            main_window.basic_vbox.add(main_window.basic_vbox.config_box)
            
class FullscreenButton(Gtk.ToggleButton):
    def __init__(self, main_window):
        Gtk.ToggleButton.__init__(self)
        icon = Gtk.Image()
        icon.set_from_stock(Gtk.STOCK_FULLSCREEN, Gtk.IconSize.BUTTON)
        label = Gtk.Label(label="Vollbild")
        label.set_hexpand(True)
        grid = Gtk.Grid.new()
        grid.set_orientation(Gtk.Orientation.HORIZONTAL)
        grid.set_column_spacing(5)
        grid.add(label)
        grid.add(icon)
        self.add(grid)
        self.connect("toggled", self.toggled, main_window)
    
    def toggled(self, button, main_window):
        if self.get_active():
            main_window.fullscreen()
        else:
            main_window.unfullscreen()

class TopGrid(Gtk.Grid):
    def __init__(self,
                 loco_treeview,
                 loco_property_table,
                 function_treeview,
                 server_table,
                 joystick_table,
                 sound_table,
                 main_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        
        button_box = Gtk.ButtonBox.new(Gtk.Orientation.HORIZONTAL)
        button_box.set_layout(Gtk.ButtonBoxStyle.START)
        button_box.set_hexpand(False)
        try:
            button_box.get_style_context().add_class(Gtk.STYLE_CLASS_LINKED)
        except AttributeError:
            pass
        self.load_button = LoadButton(loco_treeview,
                                      loco_property_table,
                                      function_treeview,
                                      server_table,
                                      joystick_table,
                                      sound_table,
                                      main_window)
        self.save_as_button = SaveAsButton(main_window)
        self.save_button = SaveButton(main_window)
        self.fullscreen_button = FullscreenButton(main_window)
        self.config_control_switch = ConfigControlSwitch(main_window)

        button_box.pack_start(self.load_button, False, False, 0)
        button_box.pack_start(self.save_as_button, False, False, 0)
        button_box.pack_start(self.save_button, False, False, 0)
        button_box.pack_start(self.fullscreen_button, False, False, 0)
        self.add(button_box)
        self.add(self.config_control_switch)

if __name__ == "__main__":
    Config = config.Config()
    GObject.threads_init() # Needed to start threads
    start_msg = " Starting Electrip Version "+ ELECTRIP_VERSION + " "
    line = " " + "-" * len(start_msg) + " "
    locked_print(line + "\n|" + start_msg + "|\n" + line)
    MainWindow()
    Gtk.main()
