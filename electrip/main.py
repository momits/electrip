#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys
# add parent-directory to sys.path,
# to allow relative imports in submodules
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from socket import error as SocketError
import gc
import argparse

from gi.repository import GObject, Gtk, GdkPixbuf, Gdk, Gio, GLib

from electrip.concurrent import locked_print
from electrip.constants import ELECTRIP_VERSION, ICON_PATHS
from electrip.widgets import StockImageButton
from electrip.config import JsonModel
from electrip import configuration_ui
from electrip import control_ui
from electrip import dialog_templates

class Electrip(Gtk.Application):
    """
    The main application.
    Creating an instance of this class and calling its
    *run*-method starts Electrip.
    Requires ``Config`` to be a global instance
    of `config.JsonModel`
    """
    def __init__(self):
        Gtk.Application.__init__(self,
                                 application_id="apps.momits.electrip",
                                 flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        
        fullscreen = Gio.SimpleAction.new_stateful("toggle_fullscreen",
                                                   None,
                                                   GLib.Variant.new_boolean(False))
        fullscreen.connect("activate", self.toggle_fullscreen)
        self.add_action(fullscreen)
        self.add_accelerator("F11", "app.toggle_fullscreen", None)
        
        load = Gio.SimpleAction.new("load_file", None)
        load.connect("activate", self.load_file_with_dialog)
        self.add_action(load)
        self.add_accelerator("<Control>O", "app.load_file", None)
        
        save = Gio.SimpleAction.new("save_file", None)
        save.set_enabled(False)
        save.connect("activate", self.save_file)
        self.add_action(save)
        self.add_accelerator("<Control>S", "app.save_file", None)
        
        save_as = Gio.SimpleAction.new("save_file_as", None)
        save_as.connect("activate", self.save_file_as)
        self.add_action(save_as)
        
        self.last_visible_view = "config"
        # flag to indicate whether electrip is supposed to quit
        self.quitting = False
        self.control_box = None
        
        try:
            screen = Gdk.Screen.get_default()
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path("gtk_styles_and_transitions.css")
            context = Gtk.StyleContext()
            context.add_provider_for_screen(screen,
                                            css_provider,
                                            Gtk.STYLE_PROVIDER_PRIORITY_USER)
        # Electrip shouldn't break if special themeing is not available
        except:
            pass
    
        
    def do_command_line(self, args):
        """
        Handler method for command line arguments,
        such as ``--file``.
        """
        Gtk.Application.do_command_line(self, args)
        parser = argparse.ArgumentParser(prog='gui')
        parser.add_argument('-f', '--file', action='store')
        self.args = parser.parse_args(args.get_arguments()[1:])
        self.do_activate()
        return 0
        
    def do_activate(self):
        """
        Builds the gui, connects signals and shows it.
        """
        builder = Gtk.Builder()
        builder.add_from_file("electrip.ui")
        builder.connect_signals({"on_delete_event": self.prepare_quit,
                                 "on_view_switched": self.toggle_view})
        
        self.window = builder.get_object("electrip_main_window")
        self.add_window(self.window)
        
        self.config_box = configuration_ui.MainBox(Config, self.window)
        self.control_wrapper_box = Gtk.EventBox()
        
        stack = builder.get_object("main_stack")
        stack.add_titled(self.config_box,
                         "config",
                         "Konfiguration")
        
        stack.add_titled(self.control_wrapper_box,
                         "control",
                         "Steuerung")
        
        self.window.maximize()
        self.window.show_all()
        
        if self.args.file:
            if self.load_file(self.args.file):
                stack.set_visible_child_name("control")
        
        Config.new_unsaved_changes_method = self.new_unsaved_changes
        Config.notice_unsaved_changes = True
        
    def load_file_with_dialog(self, unused_action, unused_parameter):
        """
        Shows a file-chooser dialog to select a file to load.
        """
        file_chooser_dialog = dialog_templates.FileLoadDialog(self.window)
        file_chooser_dialog.set_filename(Config.last_file)
        response = file_chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            path = file_chooser_dialog.get_filename()
            self.load_file(path)
        elif response == Gtk.ResponseType.CANCEL:
            locked_print("Laden abgebrochen.")
        file_chooser_dialog.destroy()
        
    def load_file(self, path):
        """
        Tries to load the configuration from *path*.
        Without user interaction.
        """
        try:
            Config.load(path)
        except ValueError:
            self.error_dialog("Die Datei ist ungültig! "
                              "Konnte Konfiguration nicht laden.")
            return False
        except IOError:
            self.error_dialog("Der Dateipfad ist ungültig!"
                              "Konnte Konfiguration nicht laden.")
            return False
        except KeyError:
            self.error_dialog("Ein Parameter konnte nicht geladen werden, "
                              "eventuell handelt es ich um eine ältere Electrip-Datei.")
            return False
        except:
            self.error_dialog("Beim Laden der Datei ist ein unbekannter "
                              "Fehler aufgetreten - es handelt sich nicht "
                              "um eine gültige Electrip-Datei.")
            return False
        else:
            self.config_box.loco_scrolled_window.treeview.load()
            self.config_box.joystick_table.load(Config.joystick)
            self.config_box.server_table.load(Config.server)
            self.config_box.sound_table.load(Config.sound)
            
            if self.last_visible_view == "control":
                self.control_box.quit()
                gc.collect()
                self.control_box = control_ui.MainBox(Config, self.window)
                self.control_wrapper_box.add(self.control_box)

            self.window.set_title("Electrip " + ELECTRIP_VERSION + " - " + path)
            return True
    
    def save_file(self, unused_action, unused_parameter):
        """
        Saves the currently opened configuration
        at the same location, overwriting the old file.
        """
        Config.save(Config.last_file)
        self.lookup_action("save_file").set_enabled(False)
    
    def save_file_as(self, unused_action, unused_parameter):
        """
        Opens a :class:`FileSaveDialog`, allowing the user
        to select a destination. Saves the config there.
        """
        file_chooser_dialog = dialog_templates.FileSaveDialog(self.window)
        file_chooser_dialog.set_filename(Config.last_file)
        response = file_chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            path = file_chooser_dialog.get_filename()
            # if a file-name was chosen but ending is missing, add ending
            if path != "" and path[len(path) - 5:len(path)] != ".json":
                path += ".json"
            Config.save(path)
            self.lookup_action("save_file").set_enabled(False)
            self.window.set_title("Electrip " + ELECTRIP_VERSION + " - " + path)
        file_chooser_dialog.destroy()
        
    def new_unsaved_changes(self):
        """
        Handler for unsaved changes, enables the "save_file"-action.
        """
        self.lookup_action("save_file").set_enabled(True)
        
    def prepare_quit(self, window, event):
        response = 1
        if Config.has_unsaved_changes:
            dialog = Gtk.MessageDialog(self.window,
                                       0,
                                       Gtk.MessageType.QUESTION,
                                       Gtk.ButtonsType.NONE,
                                       "Die Datei besitzt ungespeicherte Änderungen.\n"
                                       "Wollen Sie diese speichern?")
            dialog.add_buttons("Speichern", 0,
                               "Verwerfen und Electrip beenden", 1,
                               "Abbrechen", 2)
            response = dialog.run()
            dialog.destroy()
            if response == 0 and Config.opened_file == None:
                self.activate_action("save_file_as", None)
            elif response == 0:
                self.activate_action("save_file", None)
        if response != 2:
            if self.control_box != None:
                self.control_box.quit()
            self.quitting = True
            self.quit()
            locked_print("Electrip wurde beendet.")
        else:
            dialog.destroy()
            return True
        
    def toggle_fullscreen(self, action, unused_parameter):
        # toggle the action state and change to fullscreen
        action.set_state(GLib.Variant.new_boolean(not action.get_state()))
        if self.window.get_window().get_state() & Gdk.WindowState.FULLSCREEN == 0:
            self.window.fullscreen()
        else:
            self.window.unfullscreen()
            
    def toggle_view(self, stack, unused_propinfo):
        visible_view = stack.get_visible_child_name()
        if None != visible_view != self.last_visible_view \
        and not self.quitting:
            if visible_view == "control":
                try:
                    self.control_box = control_ui.MainBox(Config,
                                                          self.window)
                except SocketError:
                    self.error_dialog("Es konnte keine Verbindung zum "
                                      "SRCP-Server aufgebaut werden.\n"
                                      "Überprüfen Sie die Server-Einstellungen "
                                      "(Host, Port ...).\nIst der SRCP-Server aktiv?")
                    stack.set_visible_child_name("config")
                else:
                    self.control_wrapper_box.add(self.control_box)
            elif self.control_box != None:
                self.control_box.quit()
                self.control_box = None
                
                # Collect the objects which have been freed in the "quit"-methods
                gc.collect()
                
                # TODO: enable for Gtk+ 3.11
#                 self.transition_handler_id = stack.connect("notify::transition-running",
#                                                            self.quit_control_handler)
            self.last_visible_view = visible_view
    
# TODO: enable for Gtk+ 3.11
#     def quit_control_handler(self, *args):
#         self.control_box.quit()
#         self.control_box = None
#         stack.disconnect(self.transition_handler_id)
    
    def error_dialog(self, warning):
        """
        Shows an error-dialog displaying *warning*.
        """
        error_dialog = Gtk.MessageDialog(self.window,
                                         0,
                                         Gtk.MessageType.ERROR,
                                         Gtk.ButtonsType.CLOSE,
                                         warning)
        error_dialog.run()
        error_dialog.destroy()

if __name__ == "__main__":
    Config = JsonModel()
    # Needed to start threads:
    GObject.threads_init()
    start_msg = " Starting Electrip Version "+ ELECTRIP_VERSION + " "
    line = " " + "-" * len(start_msg) + " "
    locked_print(line + "\n|" + start_msg + "|\n" + line)
    app = Electrip()
    app.run(sys.argv)
