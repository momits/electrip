#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import gettext
import locale
import logging
from socket import error as SocketError
import gc
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk, GdkPixbuf, Gdk, Gio, GLib

from electrip.constants import ELECTRIP_VERSION, ICON_PATHS, PATH, LOCALE_PATH
from electrip.config import JsonModel
from electrip import configuration_ui
from electrip import control_ui
from electrip import dialog_templates

logger = logging.getLogger(__name__)

_ = gettext.translation("main", localedir=LOCALE_PATH).gettext
locale.bindtextdomain("main", LOCALE_PATH)  # set the global textdomain for GtkBuilder


class Electrip(Gtk.Application):
    """
    The main application.
    Creating an instance of this class and calling its
    *run*-method starts Electrip.
    Requires ``Config`` to be a global instance
    of `config.JsonModel`
    """
    def __init__(self):
        global Config
        Config = JsonModel()

        self.file_name_arg = None

        # Needed to start parallel threads later on:
        GObject.threads_init()

        Gtk.Application.__init__(self,
                                 application_id="apps.momits.Electrip",
                                 flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

        self.add_main_option("file", ord("f"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.FILENAME, _("Open existing configuration"), None)

        fullscreen = Gio.SimpleAction.new_stateful("toggle-fullscreen",
                                                   None,
                                                   GLib.Variant.new_boolean(False))
        fullscreen.connect("activate", self.toggle_fullscreen)
        self.add_action(fullscreen)
        self.add_accelerator("F11", "app.toggle-fullscreen", None)

        unfullscreen = Gio.SimpleAction.new("unfullscreen", None)
        unfullscreen.connect("activate", self.unfullscreen)
        self.add_action(unfullscreen)
        self.add_accelerator("Escape", "app.unfullscreen", None)

        load = Gio.SimpleAction.new("load-file", None)
        load.connect("activate", self.load_file_with_dialog)
        self.add_action(load)
        self.add_accelerator("<Control>O", "app.load-file", None)

        save = Gio.SimpleAction.new("save-file", None)
        save.set_enabled(False)
        save.connect("activate", self.save_file)
        self.add_action(save)
        self.add_accelerator("<Control>S", "app.save-file", None)

        save_as = Gio.SimpleAction.new("save-file-as", None)
        save_as.connect("activate", self.save_file_as)
        self.add_accelerator("<Control><Shift>S", "app.save-file-as", None)
        self.add_action(save_as)

        self.last_visible_view = "config"
        # flag to indicate whether electrip is supposed to quit
        self.quitting = False
        self.control_box = None

        screen = Gdk.Screen.get_default()
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(os.path.join(PATH, "css/electrip.css"))
        context = Gtk.StyleContext()
        context.add_provider_for_screen(screen,
                                        css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def do_command_line(self, command_line):
        """
        Handler method for command line arguments,
        such as ``--file``.
        """
        options = command_line.get_options_dict()
        try:
            self.file_name_arg = options.lookup_value("file").get_bytestring().decode("utf8")
        except (AttributeError, UnicodeDecodeError):
            pass
        self.activate()
        return 0

    def do_activate(self):
        """
        Builds the gui, connects signals and shows it.
        """
        builder = Gtk.Builder.new_from_file(os.path.join(PATH, "electrip.ui"))
        builder.connect_signals({"on_delete_event": self.prepare_quit,
                                 "on_view_switched": self.toggle_view})

        self.window = builder.get_object("electrip_main_window")
        self.window.set_title("Electrip " + ELECTRIP_VERSION)
        self.window.set_icon_list([GdkPixbuf.Pixbuf.new_from_file(path)
                                   for path in ICON_PATHS])
        self.add_window(self.window)

        self.config_box = configuration_ui.MainBox(Config, self.window)
        self.control_wrapper_box = Gtk.EventBox()

        stack = builder.get_object("main_stack")
        stack.add_titled(self.config_box,
                         "config",
                         _("Configure"))

        stack.add_titled(self.control_wrapper_box,
                         "control",
                         _("Control"))

        self.window.maximize()
        self.window.show_all()

        if self.file_name_arg:
            if self.load_file(self.file_name_arg):
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
            logger.info("Laden abgebrochen.")
        file_chooser_dialog.destroy()

    def load_file(self, path):
        """
        Tries to load the configuration from *path*.
        Without user interaction.
        """
        try:
            Config.load(path)
        except ValueError:
            self.error_dialog(_("File is invalid! "
                                "Could not load configuration."))
            return False
        except IOError:
            self.error_dialog(_("File is invalid! "
                                "Could not load configuration."))
            return False
        except KeyError:
            self.error_dialog(_("A parameter is missing in the configuration. "
                                "Maybe you loaded an outdated Electrip file."))
            return False
        except:
            self.error_dialog(_("An unknown error occurred while loading the chosen file. "
                                "It is not a valid Electrip file."))
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
        self.lookup_action("save-file").set_enabled(False)

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
            self.lookup_action("save-file").set_enabled(False)
            self.window.set_title("Electrip " + ELECTRIP_VERSION + " - " + path)
        file_chooser_dialog.destroy()

    def new_unsaved_changes(self):
        """
        Handler for unsaved changes, enables the "save-file"-action.
        """
        self.lookup_action("save-file").set_enabled(True)

    def prepare_quit(self, window, event):
        response = 1
        if Config.has_unsaved_changes:
            dialog = Gtk.MessageDialog(self.window,
                                       0,
                                       Gtk.MessageType.QUESTION,
                                       Gtk.ButtonsType.NONE,
                                       _("The file has unsaved changes.\n"
                                         "Do you want to save them?"))
            dialog.add_buttons(_("Save and exit"), 0,
                               _("Discard and exit"), 1,
                               _("Back to Electrip"), 2)
            response = dialog.run()
            dialog.destroy()
            if response == 0 and Config.opened_file == None:
                self.activate_action("save-file-as", None)
            elif response == 0:
                self.activate_action("save-file", None)
        if response != 2:
            if self.control_box != None:
                self.control_box.quit()
            self.quitting = True
            self.quit()
            logger.info(_("Electrip was quit."))
        else:
            dialog.destroy()
            return True

    def unfullscreen(self, action, unused_parameter):
        self.window.unfullscreen()

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
                    self.error_dialog(_("Electrip cannot connect to the "
                                        "SRCP server.\n"
                                        "Please check the server configuration "
                                        "(host and port).\nIs the SRCP server running?"))
                    stack.set_visible_child_name("config")
                else:
                    self.control_wrapper_box.add(self.control_box)
            elif self.control_box is not None:
                # Collect the objects which have been freed in the "quit"-methods
                gc.collect()

                self.transition_handler_id = stack.connect("notify::transition-running",
                                                           self.quit_control_handler)
            self.last_visible_view = visible_view

    def quit_control_handler(self, stack, *args):
        self.control_box.quit()
        self.control_box = None
        stack.disconnect(self.transition_handler_id)

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
