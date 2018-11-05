#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import gettext

import os
from gi.repository import GObject, Gtk, Gdk
from zipfile import BadZipfile

from electrip.constants import PROTOCOLS, RELOAD_GRAPH_IMAGE_PATH, PATH, LOCALE_PATH, APP_ID
from electrip.widgets import StockImageButton
from electrip.dialog_templates import SoundFileFilter, WarningDialog, \
    LocoLoadDialog, LocoSaveDialog, SoundLoadDialog
from electrip import config
from electrip import widgets
from electrip.config import vocab

_ = gettext.translation(APP_ID + "-configuration", localedir=LOCALE_PATH).gettext


class MainBox(Gtk.Notebook):
    """
    Root-widget containing the configuration-UI.
    """

    def __init__(self, config, main_window):
        Gtk.Notebook.__init__(self)

        global Config
        Config = config
        self.function_frame = FunctionFrame()
        self.speed_frame = SpeedGraphFrame(main_window)
        self.loco_properties_frame = LocoPropertiesFrame(self.speed_frame,
                                                         main_window)
        self.decoder_frame = DecoderFrame(self.speed_frame,
                                          main_window)

        self.loco_scrolled_window = widgets.ScrolledTreeView(LocoTreeView(self.loco_properties_frame,
                                                                          self.decoder_frame,
                                                                          self.function_frame,
                                                                          self.speed_frame))
        self.buttonbox_loco = LocoActionBox(self.loco_scrolled_window.treeview,
                                            self.loco_properties_frame,
                                            self.decoder_frame,
                                            self.function_frame,
                                            self.speed_frame)

        self.loco_grid = Gtk.Grid()
        self.loco_grid.attach(self.loco_scrolled_window,
                              0, 0, 2, 1)
        self.loco_grid.attach(self.buttonbox_loco,
                              0, 1, 2, 1)
        self.loco_grid.attach(LoadLocoButton(main_window,
                                             self.loco_scrolled_window.treeview),
                              0, 2, 1, 1)
        self.loco_grid.attach(SaveLocoButton(main_window),
                              1, 2, 1, 1)

        self.scrolled_window_loco_properties = Gtk.ScrolledWindow()
        self.loco_properties_grid = Gtk.Grid()
        self.loco_properties_grid.attach(self.loco_properties_frame,
                                         0, 0, 1, 1)
        self.loco_properties_grid.attach(self.decoder_frame,
                                         0, 1, 1, 1)
        self.loco_properties_grid.attach(self.function_frame,
                                         1, 0, 1, 2)
        self.loco_properties_grid.attach(self.speed_frame,
                                         0, 2, 2, 1)
        self.scrolled_window_loco_properties.add_with_viewport(self.loco_properties_grid)

        paned = Gtk.Paned()
        paned.set_orientation(Gtk.Orientation.HORIZONTAL)
        paned.add1(self.loco_grid)
        paned.add2(self.scrolled_window_loco_properties)
        self.append_page(paned, Gtk.Label(_("Locos")))

        self.server_table = ServerTable()
        self.append_page(widgets.TopAlignment(self.server_table),
                         Gtk.Label(_("SRCP server")))

        self.joystick_table = JoystickTable()
        self.append_page(widgets.TopAlignment(self.joystick_table),
                         Gtk.Label(_("Gamepad")))

        self.sound_table = SoundTable()
        self.append_page(widgets.TopAlignment(self.sound_table),
                         Gtk.Label(_("Sound")))
        self.show_all()


class FunctionFrame(widgets.TreeViewFrame):
    """
    Frame hosting the :class:`FunctionTreeView`.
    """

    def __init__(self):
        self.treeview = FunctionTreeView()
        self.action_box = FunctionActionBox(self.treeview)
        widgets.TreeViewFrame.__init__(self,
                                       _("Functions"),
                                       self.treeview,
                                       self.action_box)
        self.set_sensitive(False)


class EventSoundFrame(widgets.TreeViewFrame):
    """
    Frame hosting the :class:`EventSoundTreeView`.
    """

    def __init__(self, popup):
        self.treeview = EventSoundTreeView(popup)
        self.action_box = EventSoundActionBox(self.treeview)
        widgets.TreeViewFrame.__init__(self,
                                       _("Sound events"),
                                       self.treeview,
                                       self.action_box)


class FunctionSoundFrame(widgets.TreeViewFrame):
    """
    Frame hosting the :class:`FunctionSoundTreeView`.
    """

    def __init__(self, popup):
        self.treeview = FunctionSoundTreeView(popup)
        self.action_box = FunctionSoundActionBox(self.treeview)
        widgets.TreeViewFrame.__init__(self,
                                       _("Sound functions"),
                                       self.treeview,
                                       self.action_box)


class ControlPointPopup(Gtk.Window):
    """
    A popup which allows to specify a point in a
    coordinate system using two :class:`Gtk.SpinButton`-
    widgets.
    *x_var_name* and *y_var_name* specify the variable
    names for the horizontal (x) and vertical (y) axes.
    """

    __gsignals__ = {
        "add-control-point": (GObject.SIGNAL_RUN_FIRST, None,
                              (float, float))
    }

    def __init__(self, main_window, x_var_name, y_var_name):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_transient_for(main_window)
        self.set_modal(True)
        self.set_title(_("Add control point"))

        x_label = Gtk.Label.new(x_var_name)
        y_label = Gtk.Label.new(y_var_name)
        self.x_spin_button = Gtk.SpinButton.new_with_range(0.1, 10, 0.1)
        self.y_spin_button = Gtk.SpinButton.new_with_range(0.1, 10, 0.1)

        cancel_button = StockImageButton(_("Cancel"),
                                         Gtk.STOCK_CANCEL)
        cancel_button.connect("clicked", self.close)

        add_button = StockImageButton(_("Add"),
                                      Gtk.STOCK_CLOSE)
        add_button.connect("clicked", self.add_point)

        button_grid = Gtk.Grid()
        button_grid.attach(cancel_button, 0, 0, 1, 1)
        button_grid.attach(add_button, 1, 0, 1, 1)

        grid = Gtk.Grid()
        grid.attach(y_label, 0, 0, 1, 1)
        grid.attach(self.y_spin_button, 1, 0, 1, 1)
        grid.attach(x_label, 0, 1, 1, 1)
        grid.attach(self.x_spin_button, 1, 1, 1, 1)
        grid.attach(button_grid, 0, 2, 2, 1)
        self.add(grid)

    def add_point(self, unused_button):
        self.emit("add-control-point",
                  self.x_spin_button.get_value(),
                  self.y_spin_button.get_value())
        self.hide()

    def close(self, unused_button):
        self.hide()

    def setup_and_show(self, x_max, y_max):
        """
        Makes the popup visible at the mouse-position,
        with the spin-buttons accepting values between
        0 and *x_max*/*y_max*.
        """
        self.x_spin_button.set_range(0.1, x_max - 0.1)
        self.x_spin_button.set_value(x_max / 2.0)
        self.y_spin_button.set_range(0, y_max)
        self.y_spin_button.set_value(y_max / 2.0)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.show_all()


class SpeedGraphFrame(Gtk.Overlay):
    # is in fact an overlay, but uses a frame as "background", thus named *Frame*

    """
    Frame hosting the :class:`SpeedGraph`. As a subclass of
    :class:`Gtk.Overlay` it is able to display a warning screen
    and request user confirmation if one of the axes of the
    SpeedGraph has changed.
    """

    def __init__(self, main_window):
        Gtk.Overlay.__init__(self)
        frame = widgets.Frame(_("Speed mapping"))
        self.graph = SpeedGraph()
        self.engine_frame = EngineFrame(self.graph, main_window)

        control_point_button = StockImageButton(_("Add control points with "
                                                  "exact coordinates"),
                                                Gtk.STOCK_ADD)
        control_point_button.connect("clicked", self.show_control_point_popup)
        self.control_point_popup = ControlPointPopup(main_window,
                                                     self.graph.x_var_name,
                                                     self.graph.y_var_name)
        self.control_point_popup.connect("add-control-point", self.add_control_point)

        self.cancel_button = StockImageButton(_("Cancel"), Gtk.STOCK_CANCEL)
        self.cancel_button.connect("clicked", self.change_axis, False)
        self.accept_button = StockImageButton(_("Reset"), Gtk.STOCK_OK)
        self.accept_button.connect("clicked", self.change_axis, True)
        self.warn_image = Gtk.Image.new_from_file(RELOAD_GRAPH_IMAGE_PATH)
        self.warn_image.set_margin_right(7)
        self.warn_label = Gtk.Label()
        self.warn_label.set_vexpand(True)

        warn_frame = widgets.Frame(_("Reset speed mapping?"))
        warn_grid = Gtk.Grid()
        warn_grid.set_column_spacing(11)
        warn_grid.set_row_spacing(11)
        warn_grid.set_halign(Gtk.Align.CENTER)
        warn_grid.set_valign(Gtk.Align.CENTER)
        warn_grid.attach(self.warn_image, 0, 0, 1, 2)
        warn_grid.attach(self.warn_label, 1, 0, 2, 1)
        warn_grid.attach(self.cancel_button, 1, 1, 1, 1)
        warn_grid.attach(self.accept_button, 2, 1, 1, 1)
        warn_frame.add(warn_grid)
        # Gtk.EventBox draws its own background, unlike Gtk.Frame
        self.warn_box = Gtk.EventBox()
        self.warn_box.set_name("warn-box")
        self.warn_box.add(warn_frame)
        self.warn_box.show_all()

        self.grid = Gtk.Grid()
        self.grid.set_orientation(Gtk.Orientation.VERTICAL)
        self.grid.set_row_spacing(5)
        self.grid.add(self.engine_frame)
        self.grid.add(self.graph)
        self.grid.add(control_point_button)

        frame.add(self.grid)
        self.add(frame)
        self.set_sensitive(False)

        # flag indicating whether the overlay-warn-frame
        # is shown
        self.warn_frame_active = False

    def show_control_point_popup(self, unused_button):
        self.control_point_popup.setup_and_show(self.graph.x_max,
                                                self.graph.y_max)

    def add_control_point(self, unused_popup, x, y):
        self.graph.add_control_point(x, y)

    def confirm_axis_change(self,
                            message,
                            accept_callback,
                            undo_callback):
        self.control_point_popup.hide()
        self.warn_label.set_text(message)
        self.accept_callback = accept_callback
        self.undo_callback = undo_callback
        if not self.warn_frame_active:
            self.add_overlay(self.warn_box)
            self.warn_frame_active = True

    def change_axis(self, button, accept_changes):
        if accept_changes:
            self.accept_callback()
            func = self.loco.speed_to_step_func
            func.load([(0.0, 0.0),
                       (float(self.loco.max_speed),
                        float(self.loco.speed_steps))])
            self.graph.load(self.loco)
            if self.loco.engine:
                self.engine_frame.segment_bar.sounds_changed()
        else:
            self.undo_callback()
        self.remove(self.warn_box)
        self.warn_frame_active = False

    def load(self, loco):
        if self.warn_frame_active:
            self.undo_callback()
            self.remove(self.warn_box)
            self.warn_frame_active = False
        self.control_point_popup.hide()
        self.loco = loco
        self.graph.load(loco)
        self.engine_frame.load(loco)


class LoadLocoButton(Gtk.Button):
    """
    Button which opens a dialog on *main_window* for
    the import of a loco-zip-file.
    """

    def __init__(self, main_window, loco_treeview):
        Gtk.Button.__init__(self, _("Load loco"))
        self.set_valign(Gtk.Align.END)
        self.connect("clicked",
                     self.import_loco,
                     main_window,
                     loco_treeview)

    @staticmethod
    def import_loco(button, main_window, loco_treeview):
        file_chooser_dialog = LocoLoadDialog(main_window)
        response = file_chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            file_path = file_chooser_dialog.get_filename()
            try:
                Config.locos.append(Config.load_loco(file_path))
                loco_treeview.load()
            except IOError:
                main_window.error_dialog(_("A file path is invalid! "
                                           "Could not import loco."))
            except KeyError:
                main_window.error_dialog(_("A parameter is missing! "
                                           "Could not import loco."))
            except BadZipfile:
                main_window.error_dialog(_("The *.zip file has errors! "
                                           "Could not import loco."))
            except Exception as e:
                main_window.error_dialog(_("An unexpected error has occured:\n {}")
                                           .format(e))
        file_chooser_dialog.destroy()


class SaveLocoButton(Gtk.Button):
    """
    Button which opens a dialog on *main_window* for
    exporting a loco to a zip-file.
    """

    def __init__(self, main_window):
        Gtk.Button.__init__(self, _("Save loco"))
        self.set_valign(Gtk.Align.END)
        self.connect("clicked", self.export_loco, main_window)

    @staticmethod
    def export_loco(button, main_window):
        if Config.active_loco:
            file_chooser_dialog = LocoSaveDialog(main_window)
            response = file_chooser_dialog.run()
            if response == Gtk.ResponseType.OK:
                file_path = file_chooser_dialog.get_filename()
                Config.save_loco(Config.active_loco, file_path)
            file_chooser_dialog.destroy()


class LocoPropertiesFrame(widgets.Frame):
    """
    Frame for setting basic loco-properties.
    """

    def __init__(self, speed_graph_frame, main_window):
        widgets.Frame.__init__(self, _("General properties"))
        self.speed_graph_frame = speed_graph_frame

        self.table = widgets.EntryTable(True, False)
        self.table.add_float_entry(_("Maximum speed"),
                                   _("Real maximum speed of the loco in km/h"),
                                   "max_speed",
                                   1.0, 999.0, 0.1)
        self.table.add_float_entry(_("Accel. duration"),
                                   _("Time in s needed to accelerate from 0 to "
                                     "maximum speed with maximum acceleration"),
                                   "accel_duration",
                                   1.0, 9999.0, 0.1)
        self.table.add_float_entry(_("Braking duration"),
                                   _("Time in s needed to decelerate from maximum "
                                     "speed to 0 doing a full braking"),
                                   "decel_duration",
                                   1.0, 9999.0, 0.1)
        self.table.add_combo_entry(_("Travel direction"),
                                   _("Initial travel direction of the loco"),
                                   "direction",
                                   GObject.TYPE_STRING,
                                   ((True, vocab.direction[True]),
                                    (False, vocab.direction[False])))
        self.table.add_image_file_entry(_("Image"),
                                        _("An image showing the loco"),
                                        "img_path")
        self.table.add_action_button(_("Sound functions"),
                                     _("Configure sounds that can be played "
                                       "as loco functions"),
                                     _("Configure"),
                                     self.edit_function_sounds)
        self.table.add_action_button(_("Sound events"),
                                     _("Configure sounds to be played "
                                       "in the case of specific events"),
                                     _("Configure"),
                                     self.edit_event_sounds)
        self.table.add_volume_entry(_("Sound volume"),
                                    _("Sound volume of the loco"),
                                    "sound_volume")

        self.table.entry_widgets[0].connect("value-changed", self.confirm_axis_change)
        self.add(self.table)
        self.set_sensitive(False)
        self.function_sound_popup = widgets.Popup(main_window,
                                                  _("Sound functions"),
                                                  Gdk.WindowTypeHint.NORMAL)
        self.function_sound_frame = FunctionSoundFrame(self.function_sound_popup)
        self.function_sound_popup.set_content(self.function_sound_frame)

        self.event_sound_popup = widgets.Popup(main_window,
                                               _("Sound events"),
                                               Gdk.WindowTypeHint.NORMAL)
        self.event_sound_frame = EventSoundFrame(self.event_sound_popup)
        self.event_sound_popup.set_content(self.event_sound_frame)

    def load(self, loco):
        self.loading = True
        self.table.load(loco)
        self.function_sound_frame.treeview.load(loco.function_sounds)
        self.event_sound_frame.treeview.load(loco.event_sounds)
        self.loading = False

    def edit_function_sounds(self, button):
        self.function_sound_popup.show_at_mouse()

    def edit_event_sounds(self, button):
        self.event_sound_popup.show_at_mouse()

    def confirm_axis_change(self, entry):
        if not self.loading:
            self.speed_graph_frame.confirm_axis_change(_("Changing the maximum speed to "
                                                         "{} km/h will cause a reset of "
                                                         "the speed mapping!")
                                                         .format(str(entry.retrieve_value())),
                                                       self.confirm_max_speed,
                                                       self.reset_max_speed)
        else:
            self.confirm_max_speed()

    def confirm_max_speed(self):
        self.stored_max_speed = self.table.entry_widgets[0].retrieve_value()

    def reset_max_speed(self):
        self.table.entry_widgets[0].set_value(self.stored_max_speed)


class DecoderFrame(widgets.Frame):
    """
    Frame for editing the loco-properties which belong to
    the digital decoder.
    """

    def __init__(self, speed_graph_frame, main_window):
        widgets.Frame.__init__(self, _("Digital decoder"))
        self.table = DecoderTable(speed_graph_frame, main_window)
        self.add(self.table)
        self.set_sensitive(False)

    def load(self, loco):
        """
        Load the UI-values from *loco*.
        """
        self.table.load(loco)


class LocoActionBox(widgets.TreeViewActionBox):
    """
    :class:`widgets.TreeViewActionBox`-implementation
    for the :class:`LocoTreeView`.
    """

    def __init__(self,
                 loco_treeview,
                 loco_properties_frame,
                 decoder_frame,
                 function_frame,
                 speed_frame):
        self.loco_properties_frame = loco_properties_frame
        self.decoder_frame = decoder_frame
        self.function_frame = function_frame
        self.speed_frame = speed_frame
        widgets.TreeViewActionBox.__init__(self,
                                           loco_treeview,
                                           _("Add loco"),
                                           _("Remove loco"))

    def add_row_at_start(self):
        new_loco = config.Loco(Config.unsaved_changes)
        Config.locos.append(new_loco)
        self.loco_properties_frame.set_sensitive(True)
        self.decoder_frame.set_sensitive(True)
        self.function_frame.set_sensitive(True)
        self.speed_frame.set_sensitive(True)
        return [new_loco.name]

    def add_row_beneath(self, row_nr):
        new_loco = config.Loco(Config.unsaved_changes)
        Config.locos.insert(row_nr + 1, new_loco)
        # insert row with standard values after selected row
        return [new_loco.name]

    def remove_row_at(self, row_nr):
        Config.locos.pop(row_nr)
        if len(Config.locos) == 0:
            self.speed_frame.graph.clear()
            self.loco_properties_frame.set_sensitive(False)
            self.decoder_frame.set_sensitive(False)
            self.function_frame.set_sensitive(False)
            self.speed_frame.set_sensitive(False)

    def move_row_up(self, row_nr):
        Config.locos.insert(row_nr - 1,
                            Config.locos.pop(row_nr))

    def move_row_down(self, row_nr):
        Config.locos.insert(row_nr + 1,
                            Config.locos.pop(row_nr))

    def unsaved_changes(self):
        Config.unsaved_changes(Config, "locos", Config.locos)


class FunctionActionBox(widgets.TreeViewActionBox):
    """
    :class:`widgets.TreeViewActionBox`-implementation
    for the :class:`FunctionTreeView`.
    """

    def __init__(self, function_treeview):
        widgets.TreeViewActionBox.__init__(self,
                                           function_treeview,
                                           _("Add function"),
                                           _("Remove function"))

    @staticmethod
    def get_liststore_row(function):
        return [function.name,
                function.nr,
                vocab.on_off[function.state],
                function.button,
                vocab.toggle_mode[function.toggle_mode]]

    def add_row_at_start(self):
        function = config.DecoderFunction(Config.unsaved_changes)
        Config.active_loco.functions.append(function)
        return self.get_liststore_row(function)

    def add_row_beneath(self, row_nr):
        function = config.DecoderFunction(Config.unsaved_changes)
        Config.active_loco.functions.insert(row_nr + 1, function)
        return self.get_liststore_row(function)

    def remove_row_at(self, row_nr):
        Config.active_loco.functions.pop(row_nr)

    def move_row_up(self, row_nr):
        Config.active_loco.functions.insert(row_nr - 1,
                                            Config.active_loco.functions.pop(row_nr))

    def move_row_down(self, row_nr):
        Config.active_loco.functions.insert(row_nr + 2,
                                            Config.active_loco.functions.pop(row_nr))

    def unsaved_changes(self):
        Config.unsaved_changes(Config.active_loco,
                               "functions",
                               Config.active_loco.functions)


class EventSoundActionBox(widgets.TreeViewActionBox):
    """
    :class:`widgets.TreeViewActionBox`-implementation
     for the :class:`EventSoundTreeView`.
    """

    def __init__(self, event_sound_treeview):
        widgets.TreeViewActionBox.__init__(self,
                                           event_sound_treeview,
                                           _("Add sound"),
                                           _("Remove sound"))

    @staticmethod
    def get_liststore_row(event_sound):
        return [event_sound.name,
                vocab.on_off[event_sound.state],
                event_sound.button,
                event_sound.file_path,
                vocab.maybe_direction_to_str(event_sound.direction),
                vocab.maybe_float_to_str(event_sound.min_speed),
                vocab.maybe_float_to_str(event_sound.max_speed),
                vocab.maybe_float_to_str(event_sound.min_accel),
                vocab.maybe_float_to_str(event_sound.max_accel),
                event_sound.fade_in,
                event_sound.fade_out,
                vocab.on_off[event_sound.play_to_end]]

    def add_row_at_start(self):
        new_event_sound = config.EventSound(Config.unsaved_changes)
        Config.active_loco.event_sounds.append(new_event_sound)
        return self.get_liststore_row(new_event_sound)

    def add_row_beneath(self, row_nr):
        new_event_sound = config.EventSound(Config.unsaved_changes)
        Config.active_loco.event_sounds.insert(row_nr + 1,
                                               new_event_sound)
        return self.get_liststore_row(new_event_sound)

    def remove_row_at(self, row_nr):
        Config.active_loco.event_sounds.pop(row_nr)

    def move_row_up(self, row_nr):
        Config.active_loco.event_sounds.insert(row_nr - 1,
                                               Config.active_loco.event_sounds.pop(row_nr))

    def move_row_down(self, row_nr):
        Config.active_loco.event_sounds.insert(row_nr + 1,
                                               Config.active_loco.event_sounds.pop(row_nr))

    def unsaved_changes(self):
        Config.unsaved_changes(Config.active_loco,
                               "event_sounds",
                               Config.active_loco.event_sounds)


class FunctionSoundActionBox(widgets.TreeViewActionBox):
    """
    :class:`widgets.TreeViewActionBox`-implementation
    for the :class:`FunctionSoundTreeView`.
    """

    def __init__(self, event_sound_treeview):
        widgets.TreeViewActionBox.__init__(self,
                                           event_sound_treeview,
                                           _("Add sound"),
                                           _("Remove sound"))

    @staticmethod
    def get_liststore_row(func_sound):
        return [func_sound.name,
                func_sound.file_path,
                vocab.on_off[func_sound.state],
                func_sound.button,
                vocab.sound_toggle_mode[func_sound.toggle_mode]]

    def add_row_at_start(self):
        new_func_sound = config.FunctionSound(Config.unsaved_changes)
        Config.active_loco.function_sounds.append(new_func_sound)
        return self.get_liststore_row(new_func_sound)

    def add_row_beneath(self, row_nr):
        new_func_sound = config.FunctionSound(Config.unsaved_changes)
        Config.active_loco.function_sounds.insert(row_nr + 1, new_func_sound)
        return self.get_liststore_row(new_func_sound)

    def remove_row_at(self, row_nr):
        Config.active_loco.function_sounds.pop(row_nr)

    def move_row_up(self, row_nr):
        Config.active_loco.function_sounds.insert(row_nr - 1,
                                                  Config.active_loco.function_sounds.pop(row_nr))

    def move_row_down(self, row_nr):
        Config.active_loco.function_sounds.insert(row_nr + 1,
                                                  Config.active_loco.function_sounds.pop(row_nr))

    def unsaved_changes(self):
        Config.unsaved_changes(Config.active_loco,
                               "function_sounds",
                               Config.active_loco.function_sounds)


class DecoderTable(widgets.EntryTable):
    """
    UI-table for editing the loco-properties which belong to
    the digital decoder.
    """

    def __init__(self, speed_graph_frame, main_window):
        widgets.EntryTable.__init__(self, True, False)
        self.add_combo_entry(_("Protocol"),
                             _("Digital protocol of the decoder"),
                             "protocol",
                             GObject.TYPE_STRING,
                             (("M 1", vocab.protocols["M 1"]),
                              ("M 2", vocab.protocols["M 2"]),
                              ("N 1", vocab.protocols["N 1"]),
                              ("N 2", vocab.protocols["N 2"])))

        self.add_int_entry(_("Address"),
                           _("Address of the decoder"),
                           "address", 1, 10239, 1)

        self.add_combo_entry(_("Speed steps"),
                             _("Number of speed steps supported by the decoder"),
                             "speed_steps",
                             GObject.TYPE_INT,
                             ((14, 14),))

        self.add_label(_("Functions"),
                       _("Total number of functions supported "
                         "by the digital protocol"),
                       "1")

        self.speed_graph_frame = speed_graph_frame
        self.main_window = main_window
        self.protocol_combo, self.address_entry, \
        self.speed_steps_combo, self.max_function_label = self.entry_widgets
        self.protocol_combo.connect("changed", self.protocol_changed)
        self.speed_steps_combo.connect("changed", self.speed_steps_changed)
        # the output-signal is emitted whenever a new value is set for entry
        self.address_entry.connect("output", self.check_address)
        self.address_entry.connect("changed", self.address_changed)

        # flags needed for restoring logic
        self.restoring_speed_steps = False
        self.restoring_protocol = False

    def load(self, loco):
        self.loading = True
        self.loco = loco
        # sanity check: do the values we are about
        # to load comply with the rules?
        max_address, max_functions, speed_step_options = PROTOCOLS[loco.protocol]
        # only set attribute "address" if needed
        if not 1 <= loco.address <= max_address:
            loco.address = max_address
        if not loco.speed_steps in speed_step_options:
            # older Electrip-Versions allow false
            # combinations of speed_steps + protocol
            # -> in such case we overwrite the existing
            # speed-curve without warnings
            loco.speed_steps = speed_step_options[-1]
            func = loco.speed_to_step_func
            func.load([(0.0, 0.0),
                       (float(loco.max_speed),
                        float(loco.speed_steps))])

        # backup the current values as our stored values
        self.stored_protocol, self.stored_address, \
        self.stored_speed_steps, self.stored_max_functions = \
            loco.protocol, loco.address, \
            loco.speed_steps, max_functions

        # setup restrictions for the gui, eliminating wrong choices for the user
        self.restrict_to_protocol(loco.protocol)
        widgets.EntryTable.load(self, loco)
        self.loading = False

    def address_changed(self, entry):
        self.stored_address = entry.retrieve_value()

    def speed_steps_changed(self, combo):
        if not self.loading and not self.restoring_speed_steps:
            self.speed_graph_frame.confirm_axis_change(_("Changing the number of speed steps "
                                                         "to {}\n will cause a reset of the "
                                                         "speed mapping!")
                                                         .format(str(combo.retrieve_value())),
                                                       self.confirm_speed_steps,
                                                       self.reset_speed_steps)
            self.set_sensitive(False)
        else:
            self.restoring_speed_steps = False

    def confirm_speed_steps(self):
        self.stored_speed_steps = self.speed_steps_combo.retrieve_value()
        self.set_sensitive(True)

    def reset_speed_steps(self):
        self.restoring_speed_steps = True
        self.speed_steps_combo.set_value(self.stored_speed_steps)
        self.set_sensitive(True)

    def protocol_changed(self, combo):
        if not self.restoring_protocol:
            protocol = combo.retrieve_value()
            protocol_options = PROTOCOLS[protocol]
            if not self.loading:
                self.speed_graph_frame.confirm_axis_change(_("Changing the protocol to \"{}\" "
                                                             "requires\n"
                                                             "- setting the number of speed steps to {}\n"
                                                             "- restricting the address space to 1-{}\n"
                                                             "The speed mapping will be reset!")
                                                             .format(combo.retrieve_disp_value(),
                                                                     str(protocol_options[2][-1]),
                                                                     str(protocol_options[0])),
                                                           self.confirm_protocol,
                                                           self.reset_protocol)
                self.set_sensitive(False)
        else:
            self.restoring_protocol = False

    def restrict_to_protocol(self, protocol):
        max_address, max_functions, speed_step_options = PROTOCOLS[protocol]
        # Restrict range for address-entry
        self.address_entry.set_range(1, max_address)
        # Restrict options for speed-steps-combo
        liststore = Gtk.ListStore(GObject.TYPE_INT)
        disp_to_saved_vals = []
        for speed_steps in speed_step_options:
            liststore.append([speed_steps])
            disp_to_saved_vals.append((speed_steps, speed_steps))
        self.speed_steps_combo.mapping = disp_to_saved_vals
        self.speed_steps_combo.set_model(liststore)
        # Set label text
        self.max_function_label.set_text(str(max_functions))

    def confirm_protocol(self):
        protocol = self.protocol_combo.retrieve_value()
        self.restrict_to_protocol(protocol)
        self.restoring_speed_steps = True
        self.speed_steps_combo.set_value(PROTOCOLS[protocol][2][-1])
        self.confirm_speed_steps()
        self.stored_address = self.address_entry.retrieve_value()
        self.stored_protocol = self.protocol_combo.retrieve_value()
        self.stored_max_functions = self.max_function_label.get_text()
        self.set_sensitive(True)

    def reset_protocol(self):
        self.restoring_protocol = True
        self.restoring_speed_steps = True
        self.protocol_combo.set_value(self.stored_protocol)
        self.speed_steps_combo.set_value(self.stored_speed_steps)
        self.address_entry.set_value(self.stored_address)
        self.max_function_label.set_text(str(self.stored_max_functions))
        self.restoring_speed_steps = False
        self.set_sensitive(True)

    # mark the field red if the address is already used for another loco
    def check_address(self, entry, *args):
        address = entry.retrieve_value()
        if address in [loco.address
                       for loco in Config.locos if loco != self.loco]:
            entry.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 0, 0, 1))
        else:
            entry.override_color(Gtk.StateFlags.NORMAL, None)


class ServerTable(widgets.EntryTable):
    """
    UI-table for editing the properties of the TCP/IP-connection
    with the SRCP-server.
    """

    def __init__(self):
        widgets.EntryTable.__init__(self, False, True)
        self.add_string_entry(_("Host"),
                              _("IP address of the server"),
                              "host")
        self.add_int_entry(_("Port"),
                           _("Port used by the server"),
                           "port")
        self.add_int_entry(_("Bus"),
                           _("SRCP bus used to send control commands"),
                           "bus")
        self.add_bool_entry(_("Power on"),
                            _("Power on automatically when control mode is started"),
                            "power")
        self.load(Config.server)


class JoystickTable(widgets.EntryTable):
    """
    UI-table for configuring gamepad-axes and -buttons
    for general actions.
    """

    def __init__(self):
        widgets.EntryTable.__init__(self, False, True)
        self.add_int_entry(_("Emergency stop"),
                           _("Button to power off the tracks"),
                           "emergency_button")
        self.add_int_entry(_("Reverser"),
                           _("Button to reverse travel direction"),
                           "reverse_button")
        self.add_int_entry(_("Acceleration"),
                           _("Axis to control loco acceleration"),
                           "accel_axis")
        self.add_float_entry(_("Axis threshold"),
                             _("Axis deviations below this threshold will be ignored"),
                             "axis_threshold",
                             0, 0.75, 0.01)
        self.add_int_entry(_("Focus"),
                           _("Button to scroll to the currently selected loco"),
                           "focus_button")
        self.add_int_entry(_("Sound"),
                           _("Button to turn on and off the loco sound"),
                           "sound_button")
        self.add_bool_entry(_("Auto focus"),
                            _("Always focus on new loco when switching locos"),
                            "use_auto_focus")
        self.add_bool_entry(_("Button numbers"),
                            _("Display the number of the configured "
                              "gamepad button for each loco function"),
                            "show_function_nr")
        self.load(Config.joystick)


class SoundTable(widgets.EntryTable):
    """
    UI-table which allows to setup audio-playback.
    """

    def __init__(self):
        widgets.EntryTable.__init__(self, False, True)
        self.add_combo_entry(_("Sampling rate"),
                             _("Sampling rate of the used audio files"),
                             "sampling_rate",
                             GObject.TYPE_INT,
                             ((44800, 44800),
                              (44100, 44100),
                              (22050, 22050)))
        self.add_bool_entry(_("Sound level"),
                            _("Show current sound level in the speed scale"),
                            "show_level_bar")
        self.load(Config.sound)


class LocoTreeView(widgets.TreeView):
    """
    TreeView allowing to add/remove/sort locos.
    """

    def __init__(self,
                 loco_properties_frame,
                 decoder_frame,
                 function_frame,
                 speed_frame):
        self.function_frame = function_frame
        self.loco_properties_frame = loco_properties_frame
        self.decoder_frame = decoder_frame
        self.function_treeview = self.function_frame.treeview
        self.speed_frame = speed_frame

        widgets.TreeView.__init__(self, "LocoTreeView")
        self.add_text_column(_("Select loco to configure"),
                             _("Select loco"),
                             GObject.TYPE_STRING)
        self.update_model()

        self.connect("cursor-changed", self.loco_selected)
        self.set_vexpand(True)

    def loco_selected(self, treeview):
        path = self.get_cursor()[0]
        if path:
            row = path.get_indices()[0]
            Config.active_loco = Config.locos[row]
            # attention: speed-frame must be loaded first, to ensure
            # it is able to call its 'undo-callbacks' if needed
            self.speed_frame.load(Config.active_loco)
            self.function_treeview.load(Config.active_loco.functions)
            self.loco_properties_frame.load(Config.active_loco)
            self.decoder_frame.load(Config.active_loco)

    def append_loco(self, loco):
        return self.liststore.append([loco.name])

    def load(self):
        self.liststore.clear()
        if len(Config.locos) > 0:
            for loco in Config.locos:
                self.append_loco(loco)
            self.set_cursor(Gtk.TreePath.new_from_string("0"))
            self.loco_properties_frame.set_sensitive(True)
            self.decoder_frame.set_sensitive(True)
            self.function_frame.set_sensitive(True)
            self.speed_frame.set_sensitive(True)

    def save_changes(self, path, column_nr, new_value):
        Config.locos[path.get_indices()[0]].name = new_value


class FunctionTreeView(widgets.TreeView):
    """
    TreeView for the loco-functions.
    """

    def __init__(self):
        widgets.TreeView.__init__(self, "FunctionTreeView")
        self.add_text_column(_("Designation"),
                             _("Name of the function (e.g. 'Light', 'Horn')"),
                             GObject.TYPE_STRING)
        self.add_text_column(_("Function"),
                             _("Number of the function used by the "
                               "digital decoder"),
                             GObject.TYPE_INT)
        self.add_combo_column(_("State"),
                              _("Initial state of the function (On/Off)"),
                              GObject.TYPE_STRING,
                              (vocab.on_off[True], vocab.on_off[False]))
        self.add_text_column(_("Button"),
                             _("Gamepad button to trigger the function"),
                             GObject.TYPE_INT)
        self.add_combo_column(_("Trigger mode"),
                              _("How the function is triggered (push-button/switch)"),
                              GObject.TYPE_STRING,
                              (vocab.toggle_mode[config.ToggleMode.SWITCH],
                               vocab.toggle_mode[config.ToggleMode.PUSH]))
        self.update_model()

        self.set_vexpand(True)
        self.set_hexpand(True)

    def load(self, functions):
        self.liststore.clear()
        for function in functions:
            self.liststore.append([function.name,
                                   function.nr,
                                   vocab.on_off[function.state],
                                   function.button,
                                   vocab.toggle_mode[function.toggle_mode]])

    def save_changes(self, path, column_nr, new_value):
        if column_nr == 2:
            new_value = vocab.on_off[new_value]
        elif column_nr == 4:
            new_value = vocab.toggle_mode[new_value]
        setattr(Config.active_loco.functions[path.get_indices()[0]],
                Config.function_attributes[column_nr][0],
                new_value)


class EventSoundTreeView(widgets.TreeView):
    """
    TreeView which allows editing the event-sounds of
    :class:`Loco`. *popup* specifies the window this
    treeview is shown in (needed to correctly place the
    sound-file-selection-dialog).
    """

    def __init__(self, popup):
        self.popup = popup
        widgets.TreeView.__init__(self, "EventSoundTreeView")
        self.add_text_column(_("Designation"),
                             _("Name of the sound "
                               "(e.g. 'brake squeaking')"),
                             GObject.TYPE_STRING)
        self.add_combo_column(_("State"),
                              _("Initial state of the event (On/Off)"),
                              GObject.TYPE_STRING,
                              (vocab.on_off[True], vocab.on_off[False]))
        self.add_text_column(_("Gamepad button"),
                             _("Gamepad button to (de)activate watching for "
                               "the event."),
                             GObject.TYPE_INT)
        self.add_non_editable_text_column(_("Sound"),
                                          _("Sound to play at the event "
                                            ".(wav or .ogg)"),
                                          GObject.TYPE_STRING)
        self.add_combo_column(_("Travel direction"),
                              _("Travel direction of the loco"),
                              GObject.TYPE_STRING,
                              (vocab.doesnt_matter,
                               vocab.direction[True],
                               vocab.direction[False]))
        self.add_text_column(_("v<sub>min</sub>"),
                             _("Minimum speed in km/h"),
                             GObject.TYPE_STRING)
        self.add_text_column(_("v<sub>max</sub>"),
                             _("Maximum speed in km/h"),
                             GObject.TYPE_STRING)
        self.add_text_column(_("a<sub>min</sub>"),
                             _("Minimum acceleration "
                               "in km/h/s (may be negative)"),
                             GObject.TYPE_STRING)
        self.add_text_column(_("a<sub>max</sub>"),
                             _("Maximum acceleration "
                               "in km/h/s (may be negative)"),
                             GObject.TYPE_STRING)
        self.add_text_column(_("Fade-in"),
                             _("Duration of gentle fade-in in s"),
                             GObject.TYPE_FLOAT)
        self.add_text_column(_("Fade-out"),
                             _("Duration of gentle fade-out in s"),
                             GObject.TYPE_FLOAT)
        self.add_combo_column(_("Play completely"),
                              _("Whether the sound should be played "
                                "until its end even when the conditions "
                                "are no longer met"),
                              GObject.TYPE_STRING,
                              (vocab.yes_no[True],
                               vocab.yes_no[False]))
        self.update_model()

        self.connect("row-activated", self.choose_sound)
        self.set_hexpand(True)
        self.set_vexpand(True)

    def choose_sound(self, treeview, path, column):
        column_nr = column.colnr
        if column_nr == 3:
            file_chooser_dialog = SoundLoadDialog(self.popup)
            response = file_chooser_dialog.run()
            if response == Gtk.ResponseType.OK:
                file_path = file_chooser_dialog.get_filename()
                self.liststore.set_value(self.liststore.get_iter(path),
                                         column_nr,
                                         file_path)
                self.save_changes(path, column_nr, file_path)
            file_chooser_dialog.destroy()

    def load(self, event_sounds):
        """
        Populates itself from the list of :class:`EventSound`-objects
        *event_sounds*.
        """
        self.liststore.clear()
        if event_sounds:
            for event_sound in event_sounds:
                self.liststore.append([event_sound.name,
                                       vocab.on_off[event_sound.state],
                                       event_sound.button,
                                       event_sound.file_path,
                                       vocab.maybe_direction_to_str(event_sound.direction),
                                       vocab.maybe_float_to_str(event_sound.min_speed),
                                       vocab.maybe_float_to_str(event_sound.max_speed),
                                       vocab.maybe_float_to_str(event_sound.min_accel),
                                       vocab.maybe_float_to_str(event_sound.max_accel),
                                       event_sound.fade_in,
                                       event_sound.fade_out,
                                       vocab.yes_no[event_sound.play_to_end]])

            self.set_cursor(Gtk.TreePath.new_from_string("0"))

    def save_changes(self, path, column_nr, new_value):
        if column_nr == 1:
            new_value = vocab.on_off[new_value]
        elif column_nr == 4:
            new_value = vocab.str_to_maybe_direction(new_value)
        elif column_nr in [5, 6, 7, 8]:
            new_value = vocab.str_to_maybe_float(new_value)
            if new_value is None:
                self.get_model()[path][column_nr] = vocab.doesnt_matter
        elif column_nr in [9, 10]:
            new_value = max(0, new_value)
            self.get_model()[path][column_nr] = new_value
        elif column_nr == 11:
            new_value = vocab.yes_no[new_value]
        setattr(Config.active_loco.event_sounds[path.get_indices()[0]],
                Config.event_sound_attributes[column_nr][0],
                new_value)


class FunctionSoundTreeView(widgets.TreeView):
    """
    TreeView which allows editing the function-sounds of
    :class:`Loco`. *popup* specifies the window this
    treeview is shown in (needed to correctly place the
    sound-file-selection-dialog).
    """

    def __init__(self, popup):
        self.popup = popup
        widgets.TreeView.__init__(self, "FunctionSoundTreeView")

        self.add_text_column(_("Designation"),
                             _("Name of the sound "
                               "(e.g. 'brake squeaking')"),
                             GObject.TYPE_STRING)
        self.add_non_editable_text_column(_("Sound"),
                                          _("Sound to play (.wav or .ogg)"),
                                          GObject.TYPE_STRING)
        self.add_combo_column(_("State"),
                              _("Initial state of the event (On/Off)"),
                              GObject.TYPE_STRING,
                              (vocab.on_off[True], vocab.on_off[False]))
        self.add_text_column(_("Gamepad button"),
                             _("Gamepad button to trigger the sound"),
                             GObject.TYPE_INT)
        self.add_combo_column(_("Trigger mode"),
                              _("How the function is triggered"),
                              GObject.TYPE_STRING,
                              (vocab.sound_toggle_mode[config.ToggleMode.SWITCH],
                               vocab.sound_toggle_mode[config.ToggleMode.PUSH],
                               vocab.sound_toggle_mode[config.ToggleMode.PUSH_LIMITED],
                               vocab.sound_toggle_mode[config.ToggleMode.TAP]))
        self.update_model()

        self.connect("row-activated", self.choose_sound)
        self.set_hexpand(True)
        self.set_vexpand(True)

    def choose_sound(self, treeview, path, column):
        column_nr = column.colnr
        if column_nr == 1:
            file_chooser_dialog = SoundLoadDialog(self.popup)
            response = file_chooser_dialog.run()
            if response == Gtk.ResponseType.OK:
                file_path = file_chooser_dialog.get_filename()
                self.liststore.set_value(self.liststore.get_iter(path), column_nr, file_path)
                self.save_changes(path, column_nr, file_path)
            file_chooser_dialog.destroy()

    def load(self, function_sounds):
        self.liststore.clear()
        if function_sounds:
            for func_sound in function_sounds:
                self.liststore.append([func_sound.name,
                                       func_sound.file_path,
                                       vocab.on_off[func_sound.state],
                                       func_sound.button,
                                       vocab.sound_toggle_mode[func_sound.toggle_mode]])
            self.set_cursor(Gtk.TreePath.new_from_string("0"))

    def save_changes(self, path, column_nr, new_value):
        if column_nr == 2:
            new_value = vocab.on_off[new_value]
        elif column_nr == 4:
            new_value = vocab.sound_toggle_mode[new_value]
        setattr(Config.active_loco.function_sounds[path.get_indices()[0]],
                Config.function_sound_attributes[column_nr][0],
                new_value)


class SpeedGraph(widgets.ControlPointGraph):
    """
    A :class:`widgets.ControlPointGraph` for the speed-curve
    of the locos.
    """

    def __init__(self):
        widgets.ControlPointGraph.__init__(self,
                                           (_("v"), _("Speed in km/h")),
                                           (_("f"), _("Speed step")),
                                           (0.05, 0.1, 0.2, 0.25, 0.5,
                                            1, 2.5, 5, 10, 20, 50),
                                           (1, 2, 10))

    def get_func_data(self, loco):
        return loco.max_speed, loco.speed_steps, loco.speed_to_step_func

    def update_config_object(self, func):
        Config.unsaved_changes(func,
                               "control_points",
                               func.control_points)
        Config.unsaved_changes(func,
                               "func_segments",
                               func.func_segments)


class EngineDialog(WarningDialog):
    """
    Dialog asking for confirmation if the user changes the sound-model.
    """

    def __init__(self, engine_type, main_window):
        sound_labels = {config.EngineType.DIESEL: _("Combustion engine"),
                        config.EngineType.STEAM: _("Steam engine"),
                        None: _("No sound")}
        WarningDialog.__init__(self,
                               main_window,
                               _("Changing the sound model to \"{}\" "
                                 "will cause a reset of currently "
                                 "configured sounds!")
                                 .format(sound_labels[engine_type]),
                               [_("Cancel"), 0, _("Change sound model"), 1])


class EngineFrame(Gtk.Frame):
    """
    Frame for editing the :class:`Engine` of a loco. Allows setting
    the engine-type, editing the :class:`SoundSegments` of the engine
    and all other engine properties.
    """

    def __init__(self, graph, main_window):
        Gtk.Frame.__init__(self)
        self.speed_graph = graph
        self.main_window = main_window
        self.grid = Gtk.Grid()

        self.segment_bars = {}
        self.loading = False
        self.inner_margin = 10

        self.type_combo = widgets.EasyComboBox(GObject.TYPE_STRING,
                                               ((None, _("No sound")),
                                                ("steam", _("Steam engine")),
                                                ("diesel", _("Combustion engine"))))
        self.type_combo.set_valign(Gtk.Align.START)
        self.type_combo.set_halign(Gtk.Align.START)
        self.type_combo.connect("changed", self.engine_type_changed)
        self.grid.add(self.type_combo)

        self.separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        self.separator.set_margin_left(self.inner_margin)
        self.separator.set_margin_right(self.inner_margin)
        self.separator.show()

        self.set_horizontal_margins()
        self.add(self.grid)

    def load(self, loco):
        # the loco has changed -> update the type_combo + sound_options
        # prevent type_combos callback from being called
        # when a new loco is loaded
        self.loading = True
        self.loco = loco
        self.remove_sound_options()
        if loco.engine:
            self.type_combo.set_value(loco.engine.type)
            self.create_sound_options()
        else:
            self.type_combo.set_value(None)
        self.loading = False

    def create_sound_options(self):
        self.table = widgets.EntryTable(True,
                                        False,
                                        Gtk.Orientation.HORIZONTAL,
                                        3)
        if self.loco.engine.type == config.EngineType.DIESEL:
            self.table.add_sound_file_entry(_("Startup sound"),
                                            _("Sound during engine startup"),
                                            "start_sound")
            self.table.add_sound_file_entry(_("Idle sound"),
                                            _("Sound when the engine runs idle"),
                                            "idle_sound")
            self.table.add_sound_file_entry(_("Shutdown sound"),
                                            _("Sound during engine shutdown"),
                                            "quit_sound")
        else:
            self.table.add_sound_file_entry(_("Idle sound"),
                                            _("Sound when the engine runs idle"),
                                            "idle_sound")
            self.table.add_sound_file_entry(_("Steam blow sound"),
                                            _("Sound when steam leaves "
                                              "the cylinders"),
                                            "cylinder_steam_sound")
            self.table.add_int_entry(_("Strokes"),
                                     _("Number of cylinder strokes performed "
                                       "during one wheel rotation"),
                                     "nr_strokes")
            self.table.add_float_entry(_("First stroke delay"),
                                       _("Time in s between letting off steam "
                                         "and the first cylinder stroke"),
                                       "stroke_start_delay")
            self.table.add_float_entry(_("Driving wheel diameter"),
                                       _("Diameter of a driving wheel in m"),
                                       "wheel_diameter",
                                       0.1, 99, 0.001)
            self.table.add_float_entry(_("Minimum stroke frequency"),
                                       _("Lowest used frequency in strokes"
                                         " per s"),
                                       "min_freq")

        self.table.set_halign(Gtk.Align.END)
        self.table.load(self.loco.engine)
        self.table.show_all()
        self.grid.attach(self.table, 1, 0, 1, 1)

        # test if engine displayed in sound-bar is still the same as in loco (if not, new sound-bar is needed)
        if self.loco in self.segment_bars \
                and self.segment_bars[self.loco].engine == self.loco.engine:
            self.segment_bar = self.segment_bars[self.loco]
        else:
            self.segment_bar = SoundSegmentBar(self.speed_graph,
                                               self, self.main_window)
            self.segment_bar.load(self.loco)
            self.segment_bar.set_horizontal_margins(self.inner_margin - 0.5 *
                                                    self.segment_bar.handle_width)
            self.segment_bars[self.loco] = self.segment_bar
        self.grid.attach_next_to(self.separator,
                                 self.type_combo,
                                 Gtk.PositionType.BOTTOM, 2, 1)
        self.grid.attach_next_to(self.segment_bar,
                                 self.separator,
                                 Gtk.PositionType.BOTTOM, 2, 1)

    def remove_sound_options(self):
        if self.separator.get_parent():
            self.grid.remove(self.separator)
            self.grid.remove(self.segment_bar)
            self.grid.remove(self.table)
            del self.segment_bar

    def set_horizontal_margins(self):
        graph_margin_left, \
        graph_margin_right = self.speed_graph.get_needed_space()
        border = self.get_style_context().get_border(Gtk.StateFlags.NORMAL)
        margin_left = graph_margin_left - self.inner_margin - border.left
        margin_right = graph_margin_right - self.inner_margin - border.right
        self.set_margin_left(margin_left)
        self.set_margin_right(margin_right)

    # the selected value of the engine-type-combo has changed
    # -> update the loco and the sound-options
    def engine_type_changed(self, combo):
        # prevent this from being called when a new loco is loaded
        # -> we just want to display the locos engine type, not change it
        if not self.loading:
            new_engine_type = self.type_combo.retrieve_value()
            if self.loco.engine:
                engine_dialog = EngineDialog(new_engine_type, self.main_window)
                response = engine_dialog.run()
                engine_dialog.destroy()
            else:
                response = True
            if response:
                self.remove_sound_options()
                if new_engine_type is None:
                    self.loco.engine = None
                else:
                    engine = config.create_engine(new_engine_type,
                                                  Config.unsaved_changes)
                    new_segment = config.create_sound_segment(engine.type,
                                                              Config.unsaved_changes,
                                                              0,
                                                              self.loco.max_speed)
                    new_segment.set_position(config.SegmentPosition.UPPER)
                    engine.sound_segments = [new_segment]
                    engine.sound_function = config.SoundFunction(engine.sound_segments)
                    self.loco.engine = engine
                    self.create_sound_options()
            else:
                self.loading = True
                combo.set_value(self.loco.engine.type)
                self.loading = False

    def show_pause_graph(self, button):
        self.pause_graph_popup.show_at_center()

    def hide_pause_graph(self, button):
        self.pause_graph_popup.hide()


class SoundSegmentBar(Gtk.Grid):
    """
    A horizontal bar consisting of buttons which represent
    the :class:`SoundSegment`-objects of an :class:`Engine`.
    Clicking on them causes a popup to be opened, where the
    properties of the segment can be set.
    """
    # has to fit the width set in gtk_styles_and_transitions.css
    handle_width = 6

    def __init__(self, graph, speed_sound_frame, main_window):
        Gtk.Grid.__init__(self)
        self.graph = graph
        self.engine_frame = speed_sound_frame
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.left_handle = Gtk.Image.new_from_file(os.path.join(PATH, "icons", "sound_segment_bar_handle.png"))
        self.left_handle.set_halign(Gtk.Align.START)
        self.right_handle = Gtk.Image.new_from_file(os.path.join(PATH, "icons", "sound_segment_bar_handle.png"))
        self.right_handle.set_halign(Gtk.Align.END)
        self.add(self.left_handle)
        self.add(self.right_handle)
        self.set_margin_top(5)
        self.popup = widgets.Popup(main_window, "", Gdk.WindowTypeHint.DIALOG)

    def load(self, loco):
        # needed by SoundSelectorButton
        self.loco = loco
        # needed for comparison with the current loco.engine in EngineFrame
        # to find out if new soundbar is needed
        self.engine = loco.engine
        if hasattr(self, "paned"):
            self.parent_paned.destroy()
        self.paned = widgets.CustomHandlePaned()
        self.parent_paned = self.paned
        self.insert_column(1)
        self.attach(self.paned, 1, 0, 1, 1)

        # changing the position should not trigger unsaved_changes
        Config.notice_unsaved_changes = False
        for segment in loco.engine.sound_segments[:-1]:
            segment.set_position(config.SegmentPosition.MIDDLE)
        loco.engine.sound_segments[-1].set_position(config.SegmentPosition.UPPER)
        Config.notice_unsaved_changes = True
        for nr, segment in enumerate(loco.engine.sound_segments):
            button = create_sound_selector_button(loco.engine.type,
                                                  _("Sound ") + str(nr + 1),
                                                  self.popup, segment, self)
            self.paned.pack1(button, False, False)
            max_width = self.graph.get_allocated_width() - self.graph.border_left_bottom - \
                        self.graph.border_right - self.handle_width
            position = (segment.end - segment.start) / loco.max_speed * \
                       max_width - self.handle_width
            self.paned.set_position(position)
            self.paned.connect("button-release-event",
                               self.sounds_changed)

            if nr < len(loco.engine.sound_segments) - 1:
                new_paned = widgets.CustomHandlePaned()
                self.paned.pack2(new_paned, False, False)
                self.paned = new_paned
        self.show_all()

    def sounds_changed(self, *args):
        paned = self.parent_paned
        nr_handles = len(self.loco.engine.sound_segments) - 1
        width = float(paned.get_allocated_width()) - \
                nr_handles * self.handle_width
        start = 0
        for segment in self.loco.engine.sound_segments:
            child_width = float(paned.get_child1().get_allocated_width())
            segment.start = start / width * self.loco.max_speed
            segment.end = segment.start + child_width / width * \
                          self.loco.max_speed
            start += child_width
            paned = paned.get_child2()

    def set_horizontal_margins(self, margin):
        self.set_margin_left(margin)
        self.set_margin_right(margin)


def create_sound_selector_button(engine_type, *args):
    if engine_type == config.EngineType.DIESEL:
        return DieselSoundSelectorButton(*args)
    elif engine_type == config.EngineType.STEAM:
        return SteamSoundSelectorButton(*args)


class SoundSelectorButton(widgets.PopupButton):
    """
    A Button which belongs to a :class:`SoundSegment`,
    opening a popup when clicked, allowing to edit the
    segments properties.
    """

    def __init__(self, text, popup, segment, sound_bar):
        widgets.PopupButton.__init__(self, text, True, popup)

        self.grid = Gtk.Grid()

        delete_sound_button = StockImageButton(_("Delete sound"),
                                               Gtk.STOCK_DELETE)
        delete_sound_button.set_halign(Gtk.Align.START)
        delete_sound_button.connect("clicked", self.delete_sound)
        self.grid.attach(delete_sound_button, 0, 1, 1, 1)

        insert_sound_button = StockImageButton(_("Add sound segment"),
                                               Gtk.STOCK_ADD)
        insert_sound_button.set_halign(Gtk.Align.END)
        insert_sound_button.connect("clicked", self.insert_sound)
        self.grid.attach(insert_sound_button, 1, 1, 1, 1)

        self.close_button = StockImageButton(_("Close"),
                                             Gtk.STOCK_CLOSE)
        self.close_button.connect("clicked", self.hide_popup)
        self.close_button.set_halign(Gtk.Align.END)
        self.grid.attach(self.close_button, 1, 2, 1, 1)

        self.segment = segment
        self.segment_bar = sound_bar

    def set_content(self, content):
        if hasattr(self, "content"):
            self.grid.remove(self.content)
        self.content = content
        self.grid.attach(content, 0, 0, 2, 1)

    def delete_sound(self, button):
        loco = self.segment_bar.loco
        engine = loco.engine
        index = engine.sound_segments.index(self.segment)

        engine.sound_segments.remove(self.segment)
        if len(engine.sound_segments) > 0:
            prev_segment = engine.sound_segments[index - 1]
            prev_segment.end = self.segment.end
            if self.segment.position == config.SegmentPosition.UPPER:
                prev_segment.set_position(config.SegmentPosition.UPPER)
            self.segment_bar.load(loco)
            Config.unsaved_changes(loco.engine,
                                   "sound_segments",
                                   loco.engine.sound_segments)
        else:
            del self.segment_bar.engine_frame.segment_bars[loco]
            # type_combo will take care of setting loco.engine = None
            self.segment_bar.engine_frame.type_combo.set_value(None)
        self.popup.hide()

    def insert_sound(self, button):
        sound_bar = self.segment_bar
        loco = self.segment_bar.loco
        sound_segments = loco.engine.sound_segments
        border = 0.5 * (self.segment.end + self.segment.start)

        # if this segment is at the end,
        # we need to insert a SegmentPosition.UPPER-segment
        if self.segment.position == config.SegmentPosition.UPPER:
            # and replace this segment with middle-one
            self.segment.set_position(config.SegmentPosition.MIDDLE)
            new_segment = config.create_sound_segment(loco.engine.type,
                                                      Config.unsaved_changes,
                                                      border,
                                                      loco.max_speed)
            new_segment.set_position(config.SegmentPosition.UPPER)
            sound_segments.append(new_segment)
        else:
            sound_segments.insert(sound_segments.index(self.segment) + 1,
                                  config.create_sound_segment(loco.engine.type,
                                                              Config.unsaved_changes,
                                                              border,
                                                              self.segment.end))
        self.segment.end = border
        sound_bar.load(loco)
        self.popup.hide()
        Config.unsaved_changes(loco.engine,
                               "sound_segments",
                               loco.engine.sound_segments)

    def hide_popup(self, button):
        self.popup.hide()


class DieselSoundSelectorButton(SoundSelectorButton):
    """
    :class:`SoundSelectorButton`-implementation for diesel-sound.
    """

    def __init__(self, text, popup, segment, sound_bar):
        SoundSelectorButton.__init__(self, text, popup, segment, sound_bar)
        self.table = widgets.EntryTable(True, False)
        self.table.add_sound_file_entry(_("On-load:"),
                                        _("Sound to play in the chosen "
                                          "speed segment when engine "
                                          "is under load"),
                                        "load_sound")
        self.table.add_sound_file_entry(_("Acceleration:"),
                                        _("Sound to play during acceleration "
                                          "from the prior to this speed "
                                          "segment"),
                                        "accel_sound")
        if not segment.position == config.SegmentPosition.UPPER:
            self.table.add_sound_file_entry(_("Idle:"),
                                            _("Sound to play in the chosen "
                                              "speed segment when engine is "
                                              "idle"),
                                            "idle_sound")
        self.table.add_sound_file_entry(_("Braking:"),
                                        _("Sound to play during deceleration "
                                          "from this to the prior speed "
                                          "segment"),
                                        "decel_sound")
        self.set_content(self.table)

    # override standard implementation (include loading)
    def show_popup(self, button):
        self.table.load(self.segment)
        self.popup.set_content(self.grid)
        self.popup.set_title("{0:.1f}".format(self.segment.start) +
                             " bis " +
                             "{0:.1f}".format(self.segment.end) +
                             " km/h")
        self.popup.show_at_mouse()


class SteamSoundSelectorButton(SoundSelectorButton):
    """
    :class:`SoundSelectorButton`-implementation for steam-sound.
    """

    def __init__(self, text, popup, segment, sound_bar):
        SoundSelectorButton.__init__(self, text, popup, segment, sound_bar)
        self.update_stroke_sounds()

    def create_grid(self):
        grid = Gtk.Grid()
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        grid.set_column_spacing(10)
        grid.set_row_spacing(5)
        grid.set_border_width(6)
        self.buttons = []
        self.update_stroke_sounds()
        for stroke_nr in range(self.segment_bar.loco.engine.nr_strokes):
            button = widgets.EasyFileButton([SoundFileFilter()])
            button.set_tooltip_text(_("Sound for cylinder stroke {}").format(str(stroke_nr + 1)))
            path = self.segment.stroke_sounds[stroke_nr]
            if path:
                button.set_value(path)

            button.connect("file-set", self.file_set, stroke_nr)
            label = Gtk.Label(_("Stroke ") + str(stroke_nr + 1))
            label.set_halign(Gtk.Align.CENTER)
            grid.attach(label, 0, stroke_nr, 1, 1)
            grid.attach(button, 1, stroke_nr, 1, 1)
            self.buttons.append(button)
        return grid

    def update_stroke_sounds(self):
        nr_strokes = self.segment_bar.loco.engine.nr_strokes
        if self.segment.stroke_sounds is None \
                or len(self.segment.stroke_sounds) != nr_strokes:
            self.segment.stroke_sounds = [None for unused_i in range(nr_strokes)]

    def show_popup(self, button):
        self.set_content(self.create_grid())
        self.popup.set_content(self.grid)
        self.popup.set_title("{0:.1f}".format(self.segment.start) +
                             " bis " +
                             "{0:.1f}".format(self.segment.end) +
                             " km/h")
        self.popup.show_at_mouse()

    def file_set(self, button, stroke_nr):
        self.segment.stroke_sounds[stroke_nr] = button.retrieve_value()
        Config.unsaved_changes(self.segment,
                               "stroke_sounds",
                               self.segment.stroke_sounds)
