#!/usr/bin/env python
# -*- coding: utf-8 -*-
# this is ELECTRIP VERSION 2.1.6

from os import getcwd, path
package_path = path.dirname(getcwd()) # find parent-directory of current working-directory
from sys import path, argv
path.append(package_path) # add path to sys.path, to allow relative imports in submodules

from gi.repository import GObject, Gtk, GdkPixbuf
import config
Config = config.Config()
from copy import deepcopy
from Constants import ELECTRIP_VERSION, ICON_PATH_LIST
import ELECTRIP_Configuration
import SaveAndLoad
import ELECTRIP_Control
from LockedPrint import locked_print

class MainWindow(Gtk.Window):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.set_title("ELECTRIP " + ELECTRIP_VERSION + " Konfiguration")
        icon_list = [GdkPixbuf.Pixbuf.new_from_file(path) for path in ICON_PATH_LIST]
        self.set_icon_list(icon_list)
        self.connect("delete-event", self.delete_event)
        if len(argv) > 2 and (argv[1] == "-f" or argv[1] == "--file"):
            file_path = argv[2]
        else:
            file_path = None
        self.basic_vbox = BasicVBox(self)
        self.add(self.basic_vbox)
        
#        if file_path == None:
#            self.show_all()
#        else:
#            success = self.basic_vbox.buttonbox_top.load_button.load(file_path, self)
#            if success:
#                self.basic_vbox.buttonbox_top.config_control_switch.load(None, self)
#            else:
        self.maximize()
        self.show_all()
        Config.notice_unsaved_changes = True
        
    def delete_event(self, window, event):
        if Config.has_unsaved_changes:
            dialog = Gtk.MessageDialog(self,
                                       0,
                                       Gtk.MessageType.QUESTION,
                                       Gtk.ButtonsType.YES_NO,
                                       "Die Datei besitzt ungespeicherte Änderungen.\n Wollen Sie diese speichern?")
            response = dialog.run()
            dialog.destroy()
            if response == Gtk.ResponseType.YES and Config.last_file == "":
                self.basic_vbox.buttonbox_top.save_as_button.save(None, self)
            elif response == Gtk.ResponseType.YES:
                Config.save(Config.last_file)
        if self.basic_vbox.buttonbox_top.config_control_switch.control_button.get_active():
            self.basic_vbox.control_box.quit()
        Gtk.main_quit()
        locked_print("ELECTRIP wurde beendet.")
    
    def error(self, warnung):
        error_dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, warnung)
        error_dialog.run()
        error_dialog.destroy()

class BasicVBox(Gtk.Box):
    def __init__(self, main_window):
        super(BasicVBox, self).__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        
        self.config_box = ELECTRIP_Configuration.MainBox(Config, main_window)
        self.buttonbox_top = ButtonBoxTop(self.config_box.scrolled_window_loco_selection.treeview,
                                          self.config_box.loco_property_frame.table,
                                          self.config_box.loco_function_frame.scrolled_window.treeview,
                                          self.config_box.server_tab,
                                          self.config_box.joystick_tab,
                                          main_window)
        
        self.pack_start(self.buttonbox_top, False, False, 0)
        self.pack_start(self.config_box, True, True, 0)

class StockImageButton(Gtk.Button):
    def __init__(self, label, stock):
        Gtk.Button.__init__(self)
        icon = Gtk.Image()
        icon.set_from_stock(stock, Gtk.IconSize.BUTTON)
        hbox = Gtk.Box(False, 5)
        hbox.set_orientation(Gtk.Orientation.HORIZONTAL)
        if label != None:
            label = Gtk.Label(label=label)
            hbox.pack_start(label, True, True, 0)
        hbox.pack_start(icon, True, True, 0)
        self.add(hbox)

class LoadButton(StockImageButton):
    def __init__(self, loco_selection_treeview, loco_property_table, loco_function_treeview, server_tab, joystick_tab, main_window):
        StockImageButton.__init__(self, "Laden", Gtk.STOCK_OPEN)
        self.loco_selection_treeview = loco_selection_treeview
        self.loco_function_treeview = loco_function_treeview
        self.loco_property_table = loco_property_table
        self.server_tab = server_tab
        self.joystick_tab = joystick_tab
        
        self.connect("clicked", self.load_dialog, main_window)
        
    def load_dialog(self, button, main_window):
        file_chooser_dialog = SaveAndLoad.FileLoadDialog(main_window)
        file_chooser_dialog.set_filename(Config.last_file)
        response = file_chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            path = file_chooser_dialog.get_filename()
            self.load(path, main_window)
            main_window.show_all()
        elif response == Gtk.ResponseType.CANCEL:
            locked_print('Laden abgebrochen.')
        file_chooser_dialog.destroy()
        
    def load(self, path, main_window):
        try:
            Config.load(path)
            self.loco_function_treeview.load()
            self.loco_selection_treeview.load()
            self.joystick_tab.load()
            self.server_tab.load()
            if main_window.basic_vbox.buttonbox_top.config_control_switch.control_button.get_active():
                main_window.set_title("ELECTRIP " + ELECTRIP_VERSION + " Steuerung - " + path)
                new_control_box = ELECTRIP_Control.MainBox(deepcopy(Config), main_window) # deepcopy the Config so that it isn't messed up by ELECTRIP_Control
                main_window.basic_vbox.control_box.quit()
                main_window.basic_vbox.control_box = new_control_box
                main_window.basic_vbox.pack_start(main_window.basic_vbox.control_box, True, True, 0)
            else:
                main_window.set_title("ELECTRIP " + ELECTRIP_VERSION + " Konfiguration - " + path)
            return True
        except IOError:
            main_window.error("Der Dateipfad ist ungültig! Konnte Konfiguration nicht laden.")
            return False
        except KeyError:
            main_window.error("Ein Parameter konnte nicht geladen werden, evtl. handelt es ich um eine veraltete ELECTRIP-Datei.")
            return False
            
class SaveAsButton(StockImageButton):
    def __init__(self, main_window):
        StockImageButton.__init__(self, "Speichern unter", Gtk.STOCK_SAVE_AS)
        self.connect("clicked", self.save, main_window)
        
    def save(self, button, main_window):
        file_chooser_dialog = SaveAndLoad.FileSaveDialog(main_window)
        file_chooser_dialog.set_filename(Config.last_file)
        response = file_chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            path = file_chooser_dialog.get_filename()
            if path != "" and path[len(path) - 5:len(path)] != ".json": # Wenn Dateiendung fehlt und ein Dateiname angegeben wurde, Endung anhängen
                path += ".json"
            Config.save(path)
            main_window.set_title("ELECTRIP " + ELECTRIP_VERSION + " Konfiguration - " + path)
        elif response == Gtk.ResponseType.CANCEL:
            locked_print('Speichern abgebrochen.')
        file_chooser_dialog.destroy()

class SaveButton(StockImageButton):
    def __init__(self, main_window):
        StockImageButton.__init__(self, "Speichern", Gtk.STOCK_SAVE)
        self.connect("clicked", self.save, main_window)
        self.set_sensitive(False)
        
    def save(self, button, config_window): # FIXME: save-button doesn't work
        Config.save(Config.last_file)

class ConfigControlSwitch(Gtk.ButtonBox):
    def __init__(self, main_window):
        Gtk.ButtonBox.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_layout(Gtk.ButtonBoxStyle.CENTER)
        self.config_button = Gtk.RadioButton.new_with_label_from_widget(None, "Konfiguration") # Gtk.STOCK_EXECUTE
        self.pack_start(self.config_button, True, True, 0)
        
        self.control_button = Gtk.RadioButton.new_with_label_from_widget(self.config_button, "Steuerung")
        self.control_button.connect("toggled", self.toggled, main_window)
        self.pack_start(self.control_button, True, True, 0)
        main_window.control_window = None
    
    def toggled(self, button, main_window):
        if button.get_active():
            main_window.basic_vbox.remove(main_window.basic_vbox.config_box)
            main_window.basic_vbox.control_box = ELECTRIP_Control.MainBox(deepcopy(Config), main_window) # deepcopy the Config so that it isn't messed up by ELECTRIP_Control
            main_window.basic_vbox.pack_start(main_window.basic_vbox.control_box, True, True, 0)   
        else:
            if hasattr(main_window.basic_vbox, "control_box"):
                main_window.basic_vbox.control_box.quit()
            main_window.basic_vbox.pack_start(main_window.basic_vbox.config_box, True, True, 0)


class ButtonBoxTop(Gtk.Box):
    def __init__(self, loco_selection_treeview, loco_property_table, loco_function_treeview, server_tab, joystick_table, main_window):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.load_button = LoadButton(loco_selection_treeview, loco_property_table, loco_function_treeview, server_tab, joystick_table, main_window)
        self.save_as_button = SaveAsButton(main_window)
        self.save_button = SaveButton(main_window)
        self.config_control_switch = ConfigControlSwitch(main_window)

        self.pack_start(self.load_button, False, False, 0)
        self.pack_start(self.save_as_button, False, False, 0)
        self.pack_start(self.save_button, False, False, 0)
        self.pack_start(self.config_control_switch, False, False, 0)
        
if __name__ == "__main__":
    ELECTRIP = MainWindow()
    GObject.threads_init() # Needed to start socket_thread
    Gtk.main()
