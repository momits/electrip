#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import getcwd, path as os_path
package_path = os_path.dirname(getcwd()) # find parent-directory of current working-directory
from sys import path, argv
path.append(package_path) # add path to sys.path, to allow relative imports in submodules

from gi.repository import GObject, Gtk, GdkPixbuf, Gdk
import config
from copy import deepcopy
from Constants import ELECTRIP_VERSION, ICON_PATH_LIST
import Configuration
import DialogUtilities
import Control
from LockedPrint import locked_print

class MainWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_title("ELECTRIP " + ELECTRIP_VERSION)
        icon_list = [GdkPixbuf.Pixbuf.new_from_file(path) for path in ICON_PATH_LIST]
        self.set_icon_list(icon_list)
        self.connect("delete-event", self.delete_event)
        if len(argv) > 2 and (argv[1] == "-f" or argv[1] == "--file"):
            file_path = argv[2]
        else:
            file_path = None
        self.basic_vbox = BasicVBox(self)
        self.add(self.basic_vbox)
        
        if file_path != None:
            success = self.basic_vbox.top_grid.load_button.load(file_path, self)
            if success:
                self.basic_vbox.top_grid.config_control_switch.control_button.set_active(True)
        
        Config.notice_unsaved_changes = True # this  can't be set earlier, because loading process would cause unsaved changes
        self.maximize()
        self.show_all()
        
    def delete_event(self, window, event):
        if Config.has_unsaved_changes:
            dialog = Gtk.MessageDialog(self,
                                       0,
                                       Gtk.MessageType.QUESTION,
                                       Gtk.ButtonsType.YES_NO,
                                       "Die Datei besitzt ungespeicherte Änderungen.\n Wollen Sie diese speichern?")
            response = dialog.run()
            dialog.destroy()
            if response == Gtk.ResponseType.YES and Config.opened_file == None:
                self.basic_vbox.top_grid.save_as_button.save(None, self)
            elif response == Gtk.ResponseType.YES:
                Config.save(Config.last_file)
        if self.basic_vbox.top_grid.config_control_switch.control_button.get_active():
            self.basic_vbox.control_box.quit()
        Gtk.main_quit()
        locked_print("ELECTRIP wurde beendet.")
    
    def error(self, warnung):
        self.show_all()
        error_dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, warnung)
        error_dialog.run()
        error_dialog.destroy()

class BasicVBox(Gtk.Grid):
    def __init__(self, main_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        
        self.config_box = Configuration.MainBox(Config)
        self.top_grid = TopGrid(self.config_box.scrolled_window_loco_selection.treeview,
                                          self.config_box.loco_properties_frame.engine_table,
                                          self.config_box.loco_function_frame.scrolled_window.treeview,
                                          self.config_box.server_table,
                                          self.config_box.joystick_table,
                                          main_window)
        screen = Gdk.Screen.get_default()
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path('gtk_styles_and_transitions.css')
        context = Gtk.StyleContext()
        context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        
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
    def __init__(self, loco_selection_treeview, loco_property_table, loco_function_treeview, server_tab, joystick_tab, main_window):
        StockImageButton.__init__(self, "Laden", Gtk.STOCK_OPEN)
        self.loco_selection_treeview = loco_selection_treeview
        self.loco_function_treeview = loco_function_treeview
        self.loco_property_table = loco_property_table
        self.server_table = server_tab
        self.joystick_table = joystick_tab
        
        self.connect("clicked", self.load_dialog, main_window)
        
    def load_dialog(self, button, main_window):
        file_chooser_dialog = DialogUtilities.FileLoadDialog(main_window)
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
        except ValueError:
            main_window.error("Die Datei ist ungültig! Konnte Konfiguration nicht laden.")
            return False
        except IOError:
            main_window.error("Der Dateipfad ist ungültig! Konnte Konfiguration nicht laden.")
            return False
        except KeyError:
            main_window.error("Ein Parameter konnte nicht geladen werden, evtl. handelt es ich um eine veraltete ELECTRIP-Datei.")
            return False
        else:
            self.loco_function_treeview.load()
            self.loco_selection_treeview.load()
            self.joystick_table.load(Config.joystick)
            self.server_table.load(Config.server)
            if main_window.basic_vbox.top_grid.config_control_switch.control_button.get_active(): # if control is active
                if hasattr(Config, "new_unsaved_changes_method"):
                    del Config.new_unsaved_changes_method
                new_control_box = Control.MainBox(deepcopy(Config), main_window) # deepcopy the Config so that it isn't messed up by Control
                main_window.basic_vbox.control_box.quit()
                main_window.basic_vbox.control_box = new_control_box
                main_window.basic_vbox.add(main_window.basic_vbox.control_box)

            main_window.set_title("ELECTRIP " + ELECTRIP_VERSION + " - " + path)
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
            main_window.set_title("ELECTRIP " + ELECTRIP_VERSION + " - " + path)
        elif response == Gtk.ResponseType.CANCEL:
            locked_print('Speichern abgebrochen.')
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
        self.control_button.connect("toggled", self.toggled, main_window)
        self.pack_start(self.control_button, True, True, 0)
        main_window.control_window = None
    
    def toggled(self, button, main_window):
        if button.get_active():
            main_window.basic_vbox.remove(main_window.basic_vbox.config_box)
            del Config.new_unsaved_changes_method # delete any references to GObjects because they are non-copyable
            main_window.basic_vbox.control_box = Control.MainBox(deepcopy(Config), main_window) # deepcopy the Config so that it isn't messed up by Control
            main_window.basic_vbox.add(main_window.basic_vbox.control_box)
        else:
            if hasattr(main_window.basic_vbox, "control_box"):
                main_window.basic_vbox.control_box.quit()
            main_window.basic_vbox.add(main_window.basic_vbox.config_box)
            Config.new_unsaved_changes_method = main_window.basic_vbox.top_grid.save_button.new_unsaved_changes # restore references to GObjects (in this case save_button)
            
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
    def __init__(self, loco_selection_treeview, loco_property_table, loco_function_treeview, server_tab, joystick_table, main_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        
        button_box = Gtk.ButtonBox.new(Gtk.Orientation.HORIZONTAL)
        button_box.set_layout(Gtk.ButtonBoxStyle.START)
        button_box.set_hexpand(False)
        context = button_box.get_style_context()
        context.add_class(Gtk.STYLE_CLASS_LINKED)
        
        self.load_button = LoadButton(loco_selection_treeview, loco_property_table, loco_function_treeview, server_tab, joystick_table, main_window)
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
    ELECTRIP = MainWindow()
    GObject.threads_init() # Needed to start socket_thread
    Gtk.main()
