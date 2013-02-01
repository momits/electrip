#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository import GObject, Gtk, Pango, Gdk
import cairo
import config
from math import pi
from Constants import EntryTableType, SegmentPosition, EngineType, CellType,\
    ELECTRIP_VERSION, ToggleMode
from ELECTRIP import StockImageButton
from DialogUtilities import ImageFileFilter, AllFileFilter, SoundFileFilter
from LockedPrint import locked_print
import DialogUtilities

class MainBox(Gtk.Notebook):
    def __init__(self, config, main_window):
        Gtk.Notebook.__init__(self)
        global Config
        Config = config
        self.function_frame = FunctionFrame()
        self.speed_frame = SpeedGraphFrame(main_window)
        self.loco_properties_frame = LocoPropertiesFrame(main_window)

        self.scrolled_window_loco_selection = ScrolledTreeView(LocoTreeView(self.loco_properties_frame,
                                                                                     self.function_frame,
                                                                                     self.speed_frame))
        self.buttonbox_loco = LocoActionBox(self.scrolled_window_loco_selection.treeview,
                                                   self.loco_properties_frame,
                                                   self.function_frame,
                                                   self.speed_frame)
        
        self.loco_grid = Gtk.Grid()
        self.loco_grid.attach(self.scrolled_window_loco_selection, 0, 0, 1, 1)
        self.loco_grid.attach(self.buttonbox_loco, 0, 1, 1, 1)
        self.loco_grid.attach(Gtk.Separator.new(Gtk.Orientation.VERTICAL), 1, 0, 1, 2)
        
        self.scrolled_window_loco_properties = Gtk.ScrolledWindow()
        self.loco_properties_grid = Gtk.Grid()
        self.loco_properties_grid.attach(self.loco_properties_frame, 0, 0, 1, 1)
        self.loco_properties_grid.attach(self.function_frame, 1, 0, 1, 1)
        self.loco_properties_grid.attach(self.speed_frame, 0, 1, 2, 1)
        self.scrolled_window_loco_properties.add_with_viewport(self.loco_properties_grid)
        
        self.loco_grid.attach(self.scrolled_window_loco_properties, 2, 0, 1, 1)
        self.append_page(self.loco_grid, Gtk.Label("Lokomotiven"))
        
        self.server_table = ServerTable()
        self.append_page(TopAlignment(self.server_table), Gtk.Label("SRCP-Server"))
        
        self.joystick_table = JoystickTable()
        self.append_page(TopAlignment(self.joystick_table), Gtk.Label("Gamepad"))
        self.show_all()

class BoldLabel(Gtk.Label):
    def __init__(self, text):
        Gtk.Label.__init__(self)
        self.set_markup("<b>" + text + "</b>")

class TopAlignment(Gtk.Alignment):
    def __init__(self, child):
        Gtk.Alignment.__init__(self)
        self.set(0.0, 0.0, 0.0, 0.0)
        self.add(child)

class Frame(Gtk.Frame):
    def __init__(self, label=None):
        Gtk.Frame.__init__(self)
        self.set_border_width(10)
        if label != None:
            self.set_label_widget(BoldLabel(label))

class TreeViewFrame(Frame):
    def __init__(self, frame_label, treeview, button_box):
        Frame.__init__(self, frame_label)
        grid = Gtk.Grid()
        grid.attach(ScrolledTreeView(treeview), 0, 0, 1, 1)
        grid.attach(button_box, 0, 1, 1, 1)
        self.add(grid)
        
class FunctionFrame(TreeViewFrame):
    def __init__(self):
        self.treeview = FunctionTreeView()
        self.action_box = FunctionActionBox(self.treeview)
        TreeViewFrame.__init__(self, "Funktionen", self.treeview, self.action_box)
        self.set_sensitive(False)
        
class EventSoundFrame(TreeViewFrame):
    def __init__(self, popup):
        self.treeview = EventSoundTreeView(popup)
        self.action_box = EventSoundActionBox(self.treeview)
        TreeViewFrame.__init__(self, "Geräusch-Ereignisse", self.treeview, self.action_box)
        
class FunctionSoundFrame(TreeViewFrame):
    def __init__(self, popup):
        self.treeview = FunctionSoundTreeView(popup)
        self.action_box = FunctionSoundActionBox(self.treeview)
        TreeViewFrame.__init__(self, "Geräusch-Funktionen", self.treeview, self.action_box)
        
class GraphFrame(Frame):
    def __init__(self, label, warn_message):
        Frame.__init__(self, label)
        self.set_valign(Gtk.Align.START)
        self.cancel_button = StockImageButton("Abbrechen", Gtk.STOCK_CANCEL)
        self.cancel_button.connect("clicked", self.change_axes, False)
        self.accept_button = StockImageButton("Zurücksetzen", Gtk.STOCK_OK)
        self.accept_button.connect("clicked", self.change_axes, True)
        self.warn_image = Gtk.Image.new_from_stock(Gtk.STOCK_DIALOG_WARNING, Gtk.IconSize.BUTTON)
        self.warn_label = Gtk.Label(warn_message)
        self.warn_label.set_vexpand(True)
        
        self.warn_grid = Gtk.Grid()
        self.warn_grid.set_column_spacing(5)
        self.warn_grid.set_halign(Gtk.Align.CENTER)
        self.warn_grid.set_valign(Gtk.Align.CENTER)
        self.warn_grid.attach(self.warn_image, 0, 0, 1, 1)
        self.warn_grid.attach(self.warn_label, 1, 0, 2, 1)
        self.warn_grid.attach(self.cancel_button, 1, 1, 1, 1)
        self.warn_grid.attach(self.accept_button, 2, 1, 1, 1)

class SpeedGraphFrame(GraphFrame):
    notice_combo_change = False
    loco_sound_bars = {}
    
    def __init__(self, main_window):
        GraphFrame.__init__(self,"Geschwindigkeitsverlauf", "Durch Änderung der Achsen wird die Geschwindigkeitskennlinie zurückgesetzt")        
        self.graph = SpeedStepGraph()
        self.speed_sound_grid = SpeedSoundFrame(self.graph, main_window)
        liststore = Gtk.ListStore(GObject.TYPE_INT)
        for value in [14, 27, 28, 128]:
            liststore.append([value])
        self.speed_steps_combo = EasyComboBox(liststore, [(14, 14), (27, 27), (28, 28), (128, 128)])
        self.speed_steps_combo.connect("changed", self.changed)
        self.speed_steps_combo.set_tooltip_text("Die Anzahl Fahrstufen des Lokdecoders")
        self.max_speed_spin_button = Gtk.SpinButton.new_with_range(1, 999, 0.1) # lowest possible speed is 1 km/h, highest possible 999
        self.max_speed_spin_button.connect("value-changed", self.changed)
        self.max_speed_spin_button.set_tooltip_text("Die reale Höchstgeschwindigkeit der Lokomotive in km/h")
        
        self.grid = Gtk.Grid()
        self.grid.set_row_spacing(5)
        self.grid.attach(self.speed_sound_grid, 0, 1, 3, 1)
        self.grid.attach(self.graph, 0, 2, 3, 1)
        self.grid.attach(Gtk.Label("Anzahl Fahrstufen"), 0, 3, 1, 1)
        self.grid.attach(self.speed_steps_combo, 1, 3, 1, 1)
        self.grid.attach(Gtk.Label("Höchstgeschwindigkeit"), 0, 4, 1, 1)
        self.grid.attach(self.max_speed_spin_button, 1, 4, 1, 1)
        self.grid.attach(self.warn_grid, 2, 3, 1, 2)
        
        self.add(self.grid)
        self.set_sensitive(False)
    
    def changed(self, widget):
        if self.notice_combo_change:
            self.warn_grid.set_sensitive(True)
    
    def change_axes(self, widget, accept_changes):
        if accept_changes:
            new_max_speed = self.max_speed_spin_button.get_value()
#            print "type:", type(new_max_speed), "unformatted (float):", new_max_speed, "int:", int(new_max_speed)
            if self.loco.max_speed != new_max_speed:
                self.loco.max_speed = new_max_speed
                if self.loco.engine != None:
                    self.speed_sound_grid.sound_bar.sounds_changed()
            new_speed_steps = self.speed_steps_combo.retrieve_value()
            if self.loco.speed_steps != new_speed_steps:
                self.loco.speed_steps = new_speed_steps
            func = self.loco.speed_to_step_func
            func.load([(0.0, 0.0), (float(self.loco.max_speed), float(self.loco.speed_steps))])
            self.graph.load(self.loco)
        else:
            self.max_speed_spin_button.set_value(self.loco.max_speed)
            self.speed_steps_combo.set_value(self.loco.speed_steps)
        self.warn_grid.set_sensitive(False)
    
    def load(self, loco):
        self.loco = loco
        self.graph.load(loco)
        self.speed_sound_grid.load(loco)
        self.max_speed_spin_button.set_value(self.loco.max_speed)
        self.speed_steps_combo.set_value(self.loco.speed_steps)
        self.warn_grid.set_sensitive(False)

class LocoPropertiesFrame(Frame):
    loco_attributes = ["address", "protocol", "accel_duration", "direction", "img_path", None, "sound_volume"]
    def __init__(self, main_window):
        Frame.__init__(self, "Allgemeine Eigenschaften")
        self.params_w_defs = [
                              ("Adresse", "Adresse des Digital-Decoders der Lok", [EntryTableType.INT]),
                              ("Protokoll",
                               "Digitalprotokoll des Decoders",
                               [EntryTableType.COMBO, GObject.TYPE_STRING, [("M 1", "Märklin Motorola Version 1"),
                                                                            ("M 2", "Märklin Motorola Version 2"),
                                                                            ("N 1", "DCC kurzes Adressformat"),
                                                                            ("N 2", "DCC langes Adressformat")
                                                                            ]]),
                              ("Beschleunigungsdauer",
                               "Zeit in s für die Beschleunigung von 0 auf Höchstgeschw. bei voller Auslenkung des Gamepads",
                               [EntryTableType.FLOAT]),
                              ("Fahrtrichtung",
                               "Voreingestellte Fahrtrichtung der Lokomotive",
                               [EntryTableType.COMBO, GObject.TYPE_STRING, [(True, "Vorwärts"), (False, "Rückwärts")]]),
                              ("Bild",
                               "Pfad an dem das passende Lokbild abgelegt ist",
                               [EntryTableType.IMAGE_FILE]),
                              ("Geräusch-Funktionen",
                               "Wiedergabe von Geräuschdateien als Lok-Funktionen konfigurieren",
                               [EntryTableType.BUTTON, "Bearbeiten", self.edit_sounds]),
                              ("Lautstärke", "Lautstärke der Lokomotive", [EntryTableType.VOLUME])
                              ]
        self.table = EntryTable(self.params_w_defs, self.loco_attributes, True, False)
        self.add(self.table)
        self.set_sensitive(False)
        self.popup = Popup(main_window, "Geräusch-Funktionen", Gdk.WindowTypeHint.DIALOG)
        self.function_sound_frame = FunctionSoundFrame(self.popup)
        self.popup.set_content(self.function_sound_frame)

    def load(self, loco):
        self.table.load(loco)
        self.function_sound_frame.treeview.load(loco.function_sounds)
        
    def edit_sounds(self, button):
        self.popup.show_at_mouse()

class ArrowButton(Gtk.Button):
    def __init__(self, direction): # direction: True = nach oben
        Gtk.Button.__init__(self)
        if direction:
            self.set_image(Gtk.Arrow.new(Gtk.ArrowType.UP, Gtk.ShadowType.NONE))
        else:
            self.set_image(Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.NONE))

class ScrolledTreeView(Gtk.ScrolledWindow):
    def __init__(self, treeview):
        Gtk.ScrolledWindow.__init__(self)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.treeview = treeview
        natural_req = self.treeview.get_preferred_size()[1]
        self.set_size_request(natural_req.width, natural_req.height + 40)
        self.add(self.treeview)

class ActionBox(Gtk.ButtonBox):
    def __init__(self, treeview, add_row_label, remove_row_label):
        Gtk.ButtonBox.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_layout(Gtk.ButtonBoxStyle.START)
        self.set_vexpand(False)
        self.add_row_button = Gtk.Button(add_row_label)
        self.add_row_button.connect("clicked", self.add_row, treeview) # method add_row must be implemented in subclass
        self.remove_row_button = Gtk.Button(remove_row_label)
        self.remove_row_button.connect("clicked", self.remove_row, treeview)# method delete_row must be implemented in subclass
        self.move_up_button = ArrowButton(True)
        self.move_up_button.connect("clicked", self.move_row, treeview, True)
        self.move_down_button = ArrowButton(False)
        self.move_down_button.connect("clicked", self.move_row, treeview, False)
        
        self.add(self.add_row_button)
        self.add(self.remove_row_button)
        self.add(self.move_up_button)
        self.add(self.move_down_button)
        
    def move_row(self, button, treeview, direction):
        path = treeview.get_cursor()[0]
        liststore = treeview.get_model()
        if path != None:
            row = liststore.get_iter(path)
            row_nr = path.get_indices()[0]
            if direction and row_nr > 0:
                self.move_row_up(row_nr)
                prev_row = liststore.iter_nth_child(None, row_nr - 1)
                liststore.move_before(row, prev_row)
                treeview.set_cursor(liststore.get_path(row), None, False)
                self.unsaved_changes()
            elif not direction and row_nr < len(liststore) - 1:
                self.move_row_down(row_nr)
                following_row = liststore.iter_nth_child(None, row_nr + 1)
                liststore.move_after(row, following_row)
                treeview.set_cursor(liststore.get_path(row), None, False)
                self.unsaved_changes()
            else:
                locked_print("Zeile befindet sich schon am Rand, kann nicht weiter verschoben werden.")
        else:
            locked_print("Es ist keine Zeile ausgewählt, es kann nichts verschoben werden.")
                
    def add_row(self, button, treeview):
        path = treeview.get_cursor()[0]
        liststore = treeview.get_model()
        if liststore != None:
            if path == None:
                new_row = liststore.append(self.add_row_at_start())
            else:
                row = liststore.get_iter(path)
                row_nr = path.get_indices()[0]
                new_row = liststore.insert_after(row, self.add_row_beneath(row_nr))
            liststore = treeview.get_model()
            treeview.set_cursor(liststore.get_path(new_row), None, False)
            self.unsaved_changes()
        else:
            locked_print("TreeView ist leer, es kann nichts hinzugefügt werden.")
            
    def remove_row(self, button, treeview):
        path = treeview.get_cursor()[0]
        liststore = treeview.get_model()
        if path != None:
            self.remove_row_at(path.get_indices()[0])
            liststore.remove(liststore.get_iter(path)) # Zeile im Liststore löschen
            self.unsaved_changes()
        else:
            locked_print("Keine Zeile ausgewählt, es kann nichts gelöscht werden.")

class LocoActionBox(ActionBox):
    def __init__(self, loco_treeview, loco_properties_frame, function_frame, speed_frame):
        self.loco_properties_frame = loco_properties_frame
        self.function_frame = function_frame
        self.speed_frame = speed_frame
        ActionBox.__init__(self, loco_treeview, "Neue Lok", "Lok löschen")
        
    def add_row_at_start(self):
        new_loco = config.Loco(Config.unsaved_changes)
        Config.locos.append(new_loco)        
        self.loco_properties_frame.set_sensitive(True)
        self.function_frame.set_sensitive(True)
        self.speed_frame.set_sensitive(True)
        return [new_loco.name]
    
    def add_row_beneath(self, row_nr):
        new_loco = config.Loco(Config.unsaved_changes)
        Config.locos.insert(row_nr + 1, new_loco)
        return [new_loco.name] # insert row with standard values after selected row
    
    def remove_row_at(self, row_nr):
        Config.locos.pop(row_nr)
        if len(Config.locos) == 0:
            self.speed_frame.graph.clear()
            self.loco_properties_frame.set_sensitive(False)
            self.function_frame.set_sensitive(False)
            self.speed_frame.set_sensitive(False)
    
    def move_row_up(self, row_nr):
        Config.locos.insert(row_nr - 1, Config.locos.pop(row_nr))
    
    def move_row_down(self, row_nr):
        Config.locos.insert(row_nr + 1, Config.locos.pop(row_nr))
        
    def unsaved_changes(self):
        Config.unsaved_changes(Config, "locos", Config.locos)

class FunctionActionBox(ActionBox):
    def __init__(self, function_treeview):
        ActionBox.__init__(self, function_treeview, "Neue Funktion", "Funktion löschen")
        
    def get_liststore_row(self, function):
        return [function.name, function.nr, "Aus", function.button, "Umschalter"]
        
    def add_row_at_start(self):
        function = config.Function(Config.unsaved_changes)
        Config.active_loco.functions.append(function)
        return self.get_liststore_row(function)
            
    def add_row_beneath(self, row_nr):
        function = config.Function(Config.unsaved_changes)
        Config.active_loco.functions.insert(row_nr + 1, function)
        return self.get_liststore_row(function)
    
    def remove_row_at(self, row_nr):
        Config.active_loco.functions.pop(row_nr)
    
    def move_row_up(self, row_nr):
        Config.active_loco.functions.insert(row_nr - 1, Config.active_loco.functions.pop(row_nr))
    
    def move_row_down(self, row_nr):
        Config.active_loco.functions.insert(row_nr + 2, Config.active_loco.functions.pop(row_nr))
        
    def unsaved_changes(self):
        Config.unsaved_changes(Config.active_loco, "functions", Config.active_loco.functions)
        
class EventSoundActionBox(ActionBox):    
    def __init__(self, event_sound_treeview):
        ActionBox.__init__(self, event_sound_treeview, "Neues Geräusch", "Geräusch löschen")
        
    def get_liststore_row(self, event_sound):
        return [event_sound.name, event_sound.file_path, "An", "Egal", "Egal", "Egal", "Egal", "Aus", event_sound.button]
        
    def add_row_at_start(self):
        new_event_sound = config.EventSound(Config.unsaved_changes)
        Config.active_loco.engine.event_sounds.append(new_event_sound)
        return self.get_liststore_row(new_event_sound)
    
    def add_row_beneath(self, row_nr):
        new_event_sound = config.EventSound(Config.unsaved_changes)
        Config.active_loco.engine.event_sounds.insert(row_nr + 1, new_event_sound)
        return self.get_liststore_row(new_event_sound)
    
    def remove_row_at(self, row_nr):
        Config.active_loco.engine.event_sounds.pop(row_nr)
    
    def move_row_up(self, row_nr):
        Config.active_loco.engine.event_sounds.insert(row_nr - 1, Config.active_loco.engine.event_sounds.pop(row_nr))
    
    def move_row_down(self, row_nr):
        Config.active_loco.engine.event_sounds.insert(row_nr + 1, Config.active_loco.engine.event_sounds.pop(row_nr))
        
    def unsaved_changes(self):
        Config.unsaved_changes(Config.active_loco.engine, "event_sounds", Config.active_loco.engine.event_sounds)
        
class FunctionSoundActionBox(ActionBox):    
    def __init__(self, event_sound_treeview):
        ActionBox.__init__(self, event_sound_treeview, "Neues Geräusch", "Geräusch löschen")
        
    def get_liststore_row(self, func_sound):
        return [func_sound.name, func_sound.file_path, "Aus", func_sound.button, "Umschalter"]
        
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
        Config.active_loco.function_sounds.insert(row_nr - 1, Config.active_loco.function_sounds.pop(row_nr))
    
    def move_row_down(self, row_nr):
        Config.active_loco.function_sounds.insert(row_nr + 1, Config.active_loco.function_sounds.pop(row_nr))
        
    def unsaved_changes(self):
        Config.unsaved_changes(Config.active_loco, "function_sounds", Config.active_loco.function_sounds)
          
class EasyComboBox(Gtk.ComboBox): # subclassed combobox with methods allowing to easily acces the displayed value
    def __init__(self, liststore, displayed_to_saved_vals): # displayed_to_saved_vals: the names of the parameters of config_object
        Gtk.ComboBox.__init__(self)                           # (oftenshorter than the displayed ones) 
        self.displayed_to_saved_vals = displayed_to_saved_vals # howto use: displayed_to_saved_vals =  [(parameter_name1, displayed_value1), (parameter_name2 ...
        self.set_model(liststore)
        renderer = Gtk.CellRendererText()
        self.pack_start(renderer, True)
        self.add_attribute(renderer, "text", 0)
        self.set_active(0)

    def retrieve_value(self):
        displayed_value = self.get_model()[self.get_active()][0]
        for saved_val, disp_val in self.displayed_to_saved_vals:
            if displayed_value == disp_val:
                return saved_val
        
    def set_value(self, saved_value):
        for saved_val, disp_val in self.displayed_to_saved_vals:
            if saved_value == saved_val:
                for row_nr, row in enumerate(self.get_model()):
                    if disp_val in row:
                        self.set_active(row_nr)
                        break
                break

class EasyFileButton(Gtk.FileChooserButton):
    def __init__(self, file_filters=[]): # the first file_filter is the active one
        Gtk.FileChooserButton.__init__(self, Gtk.FileChooserAction.OPEN)
        if len(file_filters) > 0:
            for file_filter in file_filters:
                self.add_filter(file_filter)
            self.set_filter(file_filters[0])
        
    def retrieve_value(self):
        return self.get_filename()
    
    def set_value(self, path):
        if path != None:
            self.set_filename(path)
        else:
            self.set_filename("(keine)") # TODO: find out how to reset the filename to "None"
            self.emit("file-set")
            
class EasyVolumeButton(Gtk.VolumeButton):
    __gsignals__ = {
      "volume-set": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
    def __init__(self, file_filters=[]):
        Gtk.VolumeButton.__init__(self)
        self.retrieve_value = self.get_value
        self.connect("value-changed", self.volume_set)
        
    def volume_set(self, button, new_value):
        self.emit("volume-set")
        
class EntryTable(Gtk.Grid):
    def __init__(self,
                 params_w_defs,
                 config_object_attributes,
                 use_tooltips,
                 use_bold_params,
                 orientation=Gtk.Orientation.VERTICAL,
                 end=None):
        Gtk.Grid.__init__(self)
        self.params_w_defs = params_w_defs
        self.config_object_attributes = config_object_attributes
        
        self.set_column_spacing(10)
        self.set_row_spacing(5)
        self.set_border_width(6)
        self.entry_fields = []
        y = 0
        x = 0
        nr = 0
        for parameter, definition, input_type in self.params_w_defs:
            if input_type[0] == EntryTableType.STRING:
                entry_field = Gtk.Entry()
                entry_field.retrieve_value = entry_field.get_text
                entry_field.set_value = entry_field.set_text
                entry_field.connect("changed", self.save_changes, config_object_attributes[nr])
            elif input_type[0] == EntryTableType.INT:
                entry_field = Gtk.SpinButton.new_with_range(0, 9999, 1)
                entry_field.retrieve_value = entry_field.get_value_as_int
                entry_field.connect("value-changed", self.save_changes, config_object_attributes[nr])
            elif input_type[0] == EntryTableType.FLOAT:
                if len(input_type) > 1:
                    entry_field = Gtk.SpinButton.new_with_range(0, 9999, input_type[1])
                else:
                    entry_field = Gtk.SpinButton.new_with_range(0, 9999, 0.1)
                entry_field.retrieve_value = entry_field.get_value
                entry_field.connect("value-changed", self.save_changes, config_object_attributes[nr])
            elif input_type[0] == EntryTableType.COMBO:
                liststore = Gtk.ListStore(input_type[1])
                for saved_val, disp_val in input_type[2]:
                    liststore.append([disp_val])
                entry_field = EasyComboBox(liststore, input_type[2])
                entry_field.connect("changed", self.save_changes, config_object_attributes[nr])
            elif input_type[0] == EntryTableType.SOUND_FILE:
                entry_field = EasyFileButton([SoundFileFilter(), AllFileFilter()])
                entry_field.connect("file-set", self.save_changes, config_object_attributes[nr])
            elif input_type[0] == EntryTableType.IMAGE_FILE:
                entry_field = EasyFileButton([ImageFileFilter(), AllFileFilter()])
                entry_field.connect("file-set", self.save_changes, config_object_attributes[nr])
            elif input_type[0] == EntryTableType.BOOL:
                entry_field = Gtk.CheckButton.new()
                entry_field.retrieve_value = entry_field.get_active
                entry_field.set_value = entry_field.set_active
                entry_field.connect("toggled", self.save_changes, config_object_attributes[nr])
            elif input_type[0] == EntryTableType.VOLUME:
                entry_field = EasyVolumeButton()
                entry_field.connect("volume-set", self.save_changes, config_object_attributes[nr])
            elif input_type[0] == EntryTableType.BUTTON:
                entry_field = Gtk.Button(input_type[1])
                entry_field.connect("clicked", *input_type[2:])
            if use_bold_params:
                parameter_label = BoldLabel(parameter)
            else:
                parameter_label = Gtk.Label(parameter)
            self.attach(parameter_label, x, y, 1, 1)
                
            if use_tooltips:
                entry_field.set_tooltip_text(definition)
            else:
                definition_label = Gtk.Label(label=definition)
                definition_label.set_alignment(0, 0.5)
                self.attach(definition_label, x + 2, y, 1, 1)
            
            self.attach(entry_field, x + 1, y, 1, 1)
            self.entry_fields.append(entry_field)
            if orientation == Gtk.Orientation.VERTICAL:
                if end == None:
                    y += 1
                else:
                    if y < end - 1:
                        y += 1
                    else:
                        x += 2
                        y = 0
            else:
                if end == None:
                    x += 2
                else:
                    if x < 2 * end - 2:
                        x += 2
                    else:
                        y += 1
                        x = 0
            nr += 1
        
    def load(self, config_object):
        self.config_object = config_object
        for nr, config_attrib in enumerate(self.config_object_attributes):
            if config_attrib != None:
                try:
                    value = getattr(config_object, config_attrib)
                except AttributeError:
                    locked_print("Attribut", config_attrib, "konnte nicht gefunden werden, es handelt sich evtl. um eine veraltete ELECTRIP-Datei.")
                else:
                    self.entry_fields[nr].set_value(value)
            
    def save_changes(self, widget, config_attrib):
        value = widget.retrieve_value()
        if getattr(self.config_object, config_attrib) != value: # only set attributes when they differ from what is already saved
            setattr(self.config_object, config_attrib, value) # -> prevent signal-handler trouble on loading
        
class ServerTable(EntryTable): # every class using EntryTable defines two list: params_w_defs and some_attributes
    server_attributes = ["host", "port", "bus", "power"]
    params_w_defs = [ # the list of attributes says which attribute of index a in the config_object maps to the Entry in EntryTable with index a
                     ("Host", "IP-Adresse des Servers", [EntryTableType.STRING]),
                     ("Port", "Port unter dem der Server erreichbar ist", [EntryTableType.INT]),
                     ("Bus", "Bus auf dem Steuerungsbefehle gesendet werden sollen", [EntryTableType.INT]),
                     ("Strom", "Schalte den Strom beim Starten der Steuerung ein", [EntryTableType.BOOL])
                     ] # The list called params_w_defs works like this:
                        # (parameter as bold text, explanation of the parameter, entry-widget used to display the parameter)
    
    def __init__(self):
        EntryTable.__init__(self, self.params_w_defs, self.server_attributes, False, True)
        self.load(Config.server)

class JoystickTable(EntryTable):
    joystick_attributes = ["emergency_button", "reverse_button", "accel_axis", "focus_button", "sound_button", "use_auto_focus", "show_function_nr"]
    params_w_defs = [
                     ("Nothalt", "Button am Gamepad über den die Gleisspannung ausgeschaltet werden kann", [EntryTableType.INT]),
                     ("Richtungswender", "Button am Gamepad für Richtungswechsel", [EntryTableType.INT]),
                     ("Beschleunigung", "Achse am Gamepad für Geschwindigkeitsregelung", [EntryTableType.INT]),
                     ("Fokus", "Button am Gamepad der die zurzeit ausgewählte Lok in den im Fenster sichtbaren Bereich holt", [EntryTableType.INT]),
                     ("Geräusch", "Button am Gamepad zum Ein-/Ausschalten des Lok-Geräuschs", [EntryTableType.INT]),
                     ("Auto-Fokus", "Ausgewählte Lok immer fokussieren, wenn nur ein Gamepad angeschlossen ist", [EntryTableType.BOOL]),
                     ("Button-Nr", "Nummer des zugehörigen Gamepad-Buttons auf den Funktions-Buttons anzeigen", [EntryTableType.BOOL])
                     ] # Liste mit verständlicheren Namen für die Parameter (wird in der GUI angezeigt)
    
    def __init__(self):
        EntryTable.__init__(self, self.params_w_defs, self.joystick_attributes, False, True)
        self.load(Config.joystick)

class TreeView(Gtk.TreeView): # Basisklasse für LokTreeView, LokPropertyTreeView und FunctionTreeView
    def __init__(self, columns, column_types, name, save_method):
        self.column_types = column_types
        self.name = name
        self.save_method = save_method
        self.liststore = Gtk.ListStore(*self.column_types)
        Gtk.TreeView.__init__(self, self.liststore)
        
        single_renderers = {} # text-renderers may be used in several columns at once
        nr = 0
        for column_name, column_tooltip, cell_render_type in columns:
            label = Gtk.Label()
            label.set_markup(column_name)
            label.show()
            label.set_tooltip_text(column_tooltip)
            if cell_render_type[0] in single_renderers:
                cell_renderer = single_renderers[cell_render_type[0]]
            else:
                if cell_render_type[0] == CellType.TEXT:
                    cell_renderer = single_renderers[cell_render_type[0]] = Gtk.CellRendererText()
                    cell_renderer.set_property("editable", True)
                    cell_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
                    cell_renderer.connect("edited", self.new_value)
                if cell_render_type[0] == CellType.TEXT_NOT_EDITABLE:
                    cell_renderer = single_renderers[cell_render_type[0]] = Gtk.CellRendererText()
                    cell_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
                elif cell_render_type[0] == CellType.COMBO:
                    cell_renderer = Gtk.CellRendererCombo()
                    cell_renderer.set_property("editable", True)
                    cell_renderer.set_property("has-entry", False)
                    cell_renderer.set_property("text-column", 0)
                    cell_renderer.connect("edited", self.new_value)
                    combostore = Gtk.ListStore(cell_render_type[1])
                    for value in cell_render_type[2]:
                        combostore.append([value])
                    cell_renderer.set_property("model", combostore)
            column = Gtk.TreeViewColumn(None, cell_renderer, text=nr)
            column.set_widget(label)
            column.set_resizable(True) # Spalten vergrößerbar / verkleinerbar machen
            column.set_data("colnr", nr) # Versehe jede Spalte mit einer Nummer, zur leichten Identifizierung
            self.append_column(column)
            nr += 1
            
    def new_value(self, cellrenderer, path, new_value):
        liststore = self.get_model()
        path, column = self.get_cursor()
        column_nr = column.get_data("colnr") # Rufe zugewiesene Eigenschaft "colnr" auf (siehe oben -> 'set_data')

        if self.column_types[column_nr] == GObject.TYPE_INT:
            try:
                new_value = int(new_value)
            except ValueError:
                locked_print("Falsche Eingabe, Sie haben keinen Wert eingegeben, der in den Typ Integer umgewandelt werden kann.")
            else:
                liststore[path][column_nr] = new_value
                self.save_method(path, column_nr, new_value)
        elif self.column_types[column_nr] == GObject.TYPE_DOUBLE:
            try:
                new_value = float(new_value.replace(",", ".")) # Kommas zur Umwandlung String-->Float durch Punkte ersetzen
            except ValueError:
                locked_print("Falsche Eingabe: Sie haben keinen Wert eingegeben, der in den Typ Float umgewandelt werden kann.")
            else:
                liststore[path][column_nr] = new_value
                self.save_method(path, column_nr, new_value)
        else:
            liststore[path][column_nr] = new_value
            self.save_method(path, column_nr, new_value)
        
class FunctionTreeView(TreeView):
    columns = [ # list to set up the standard treeview: column-name, column-tooltip, renderer-id
                         ("Bezeichnung", "Name der Funktion ('Licht', 'Hupe' ...)", [CellType.TEXT]),
                         ("Funktion", "Die Nummer der Funktion im Lok-Decoder", [CellType.TEXT]),
                         ("Wert", "Voreingestellter Zustand der Funktion: An oder Aus", [CellType.COMBO, GObject.TYPE_STRING, ["An", "Aus"]]),
                         ("Gamepad-Button", "Button am Gamepad, dem die Lok-Funktion zugewiesen ist", [CellType.TEXT]),
                         ("Schaltart", "Art, mit der eine Funktion durch einen Gamepad-Button geschaltet wird: Taster oder Umschalter",
                          [CellType.COMBO, GObject.TYPE_STRING, ["Umschalter", "Taster"]])
                         ]
    column_types = [GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING]
    
    def __init__(self):
        TreeView.__init__(
            self,
            self.columns,
            self.column_types,
            "FunctionTreeView",
            self.save_changes)
        
        self.set_vexpand(True)
        self.set_hexpand(True)
    
    def load(self, functions):
        self.liststore.clear()
        for function in functions:
            if function.state:
                state = "An"
            else:
                state = "Aus"
            if function.toggle_mode == ToggleMode.PUSH:
                toggle_mode = "Taster"
            elif function.toggle_mode == ToggleMode.SWITCH:
                toggle_mode = "Umschalter"
            self.liststore.append([function.name, function.nr, state, function.button, toggle_mode])
        
    def save_changes(self, path, column_nr, new_value):
        if new_value == "An":
            new_value = True
        elif new_value == "Aus":
            new_value = False
        elif new_value == "Taster":
            new_value = ToggleMode.PUSH
        elif new_value == "Umschalter":
            new_value = ToggleMode.SWITCH
        setattr(Config.active_loco.functions[path.get_indices()[0]], Config.function_attributes[column_nr][0], new_value)
        
class LocoTreeView(TreeView):
    column_attributes = [
                         ("Zu konfigurierende Lok wählen", "Lok auswählen", [CellType.TEXT])
                         ]
    loco_attributes = ["name"]
    column_types = [GObject.TYPE_STRING]
    
    def __init__(self, loco_properties_frame, function_frame, speed_frame):
        self.function_frame = function_frame
        self.loco_properties_frame = loco_properties_frame
        self.function_treeview = self.function_frame.treeview
        self.speed_frame = speed_frame
        
        TreeView.__init__(
            self,
            self.column_attributes,
            self.column_types,
            "LocoTreeView",
            self.save_changes)

        self.connect("cursor-changed", self.loco_selected)

    def loco_selected(self, treeview):
        path = self.get_cursor()[0]
        if path != None:
            row = path.get_indices()[0]
            Config.active_loco = Config.locos[row]
            self.function_treeview.load(Config.active_loco.functions)
            self.speed_frame.notice_combo_change = False
            self.loco_properties_frame.load(Config.active_loco)
            self.speed_frame.load(Config.active_loco)
            self.speed_frame.notice_combo_change = True
        
    def append_loco(self, loco):
        return self.liststore.append([getattr(loco, attrib) for attrib in self.loco_attributes])
            
    def load(self):
        self.liststore.clear()
        if len(Config.locos) > 0:
            for loco in Config.locos:
                self.append_loco(loco)
            self.set_cursor(Gtk.TreePath.new_from_string("0"))
            self.loco_properties_frame.set_sensitive(True)
            self.function_frame.set_sensitive(True)
            self.speed_frame.set_sensitive(True)
            
    def save_changes(self, path, column_nr, new_value):
        setattr(Config.locos[path.get_indices()[0]], self.loco_attributes[column_nr], new_value)

class EventSoundTreeView(TreeView):
    column_attributes = [("Bezeichnung", "Name des Geräusches (Bremsenquietschen ...)", [CellType.TEXT]),
                         ("Geräuschdatei", "Datei für die Wiedergabe ('*.wav' oder '*.ogg')", [CellType.TEXT_NOT_EDITABLE]),
                         ("Wert", "Voreingestellter Zustand der Funktion: An oder Aus", [CellType.COMBO, GObject.TYPE_STRING, ["An", "Aus"]]),
                         ("v<sub>min</sub>", "Mindestgeschwindigkeit", [CellType.TEXT]),
                         ("v<sub>max</sub>", "Maximalgeschwindigkeit", [CellType.TEXT]),
                         ("a<sub>min</sub>", "Mindestbeschleunigung (kann negativ sein)", [CellType.TEXT]),
                         ("a<sub>max</sub>", "Maximalbeschleunigung (kann negativ sein)", [CellType.TEXT]),
                         ("Gamepad-Button", "Button am Gamepad mit dem das Geräusch aktiviert werden kann", [CellType.TEXT]),
                         ]
    column_types = [GObject.TYPE_STRING, #GObject.TYPE_DOUBLE, GObject.TYPE_DOUBLE, GObject.TYPE_DOUBLE, GObject.TYPE_DOUBLE,
                    GObject.TYPE_STRING,
                    GObject.TYPE_STRING, # we are using strings for those columns as we want to display numbers as well as text ("Egal")
                    GObject.TYPE_STRING,
                    GObject.TYPE_STRING,
                    GObject.TYPE_STRING,
                    GObject.TYPE_STRING,
                    GObject.TYPE_INT]
    def __init__(self, popup):
        self.popup = popup
        TreeView.__init__(self,
                                  self.column_attributes,
                                  self.column_types,
                                  "EventSoundTreeView",
                                  self.save_changes)
        self.connect("row-activated", self.choose_sound)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
    def choose_sound(self, treeview, path, column):
        column_nr = column.get_data("colnr")
        if column_nr == 1:
            file_chooser_dialog = DialogUtilities.SoundLoadDialog(self.popup)
            response = file_chooser_dialog.run()
            if response == Gtk.ResponseType.OK:
                file_path = file_chooser_dialog.get_filename()
                self.liststore.set_value(self.liststore.get_iter(path), column_nr, file_path)
            file_chooser_dialog.destroy()
        
    def load(self, event_sounds):
        self.liststore.clear()
        if event_sounds != None:
            for event_sound in event_sounds:
                if event_sound.state:
                    state = "An"
                else:
                    state = "Aus"
                self.liststore.append([event_sound.name,
                                       event_sound.file_path,
                                       state,
                                       self.to_string(event_sound.min_speed),
                                       self.to_string(event_sound.max_speed),
                                       self.to_string(event_sound.min_accel),
                                       self.to_string(event_sound.max_accel),
                                       event_sound.button])
                                
            self.set_cursor(Gtk.TreePath.new_from_string("0"))
            
    def to_string(self, value):
        if value == None:
            return "Egal"
        else:
            return str(value)
        
    def save_changes(self, path, column_nr, new_value):
        if new_value == "An":
            new_value = True
        elif new_value == "Aus":
            new_value = False
        if column_nr in range(3, 7):
            if new_value == "":
                new_value = None
                self.get_model()[path][column_nr] = "Egal"
            try:
                new_value = float(new_value)
            except (ValueError, TypeError):
                new_value = Config.event_sound_attributes[column_nr][1] # take standard value
                self.get_model()[path][column_nr] = "Egal"
        setattr(Config.active_loco.engine.event_sounds[path.get_indices()[0]], Config.event_sound_attributes[column_nr][0], new_value)
        
class FunctionSoundTreeView(TreeView):
    column_attributes = [("Bezeichnung", "Name des Geräusches (Bremsenquietschen ...)", [CellType.TEXT]),
                         ("Geräuschdatei", "Datei für die Wiedergabe ('*.wav' oder '*.ogg')", [CellType.TEXT_NOT_EDITABLE]),
                         ("Wert", "Voreingestellter Zustand der Funktion: An oder Aus", [CellType.COMBO, GObject.TYPE_STRING, ["An", "Aus"]]),
                         ("Gamepad-Button", "Button am Gamepad, dem die Funktion zugewiesen ist", [CellType.TEXT]),
                         ("Schaltart", "Art mit der die Funktion durch einen Gamepad-Button geschaltet wird: Taster oder Umschalter",
                          [CellType.COMBO, GObject.TYPE_STRING, ["Umschalter",
                                                                 "Taster (Einmal abspielen)",
                                                                 "Taster (Mehrmals abspielen)",
                                                                 "Anschalter (bis Geräuschende)"]]) #,
#                         ("Wiederholen", "Das Geräusch so lange wiederholen bis die Bedingungen nicht mehr erfüllt sind",
#                          [CellType.COMBO, GObject.TYPE_STRING, ["An", "Aus"]])
                         ]
    column_types = [GObject.TYPE_STRING, #GObject.TYPE_DOUBLE, GObject.TYPE_DOUBLE, GObject.TYPE_DOUBLE, GObject.TYPE_DOUBLE,
                    GObject.TYPE_STRING,
                    GObject.TYPE_STRING, # we are using strings for those columns as we want to display numbers as well as text ("Egal")
                    GObject.TYPE_INT,
                    GObject.TYPE_STRING]
    
    def __init__(self, popup):
        self.popup = popup
        TreeView.__init__(self,
                                  self.column_attributes,
                                  self.column_types,
                                  "FunctionSoundTreeView",
                                  self.save_changes)
        self.connect("row-activated", self.choose_sound)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
    def choose_sound(self, treeview, path, column):
        column_nr = column.get_data("colnr")
        if column_nr == 1:
            file_chooser_dialog = DialogUtilities.SoundLoadDialog(self.popup)
            response = file_chooser_dialog.run()
            if response == Gtk.ResponseType.OK:
                file_path = file_chooser_dialog.get_filename()
                self.liststore.set_value(self.liststore.get_iter(path), column_nr, file_path)
                self.save_changes(path, column_nr, file_path)
            file_chooser_dialog.destroy()
        
    def load(self, function_sounds):
        self.liststore.clear()
        if function_sounds != None:
            for func_sound in function_sounds:
                if func_sound.state:
                    state = "An"
                else:
                    state = "Aus"
#                if func_sound.repeat:
#                    repeat = "An"
#                else:
#                    repeat = "Aus"
                if func_sound.toggle_mode == ToggleMode.PUSH:
                    toggle_mode = "Taster (Mehrmals abspielen)"
                elif func_sound.toggle_mode == ToggleMode.PUSH_LIMITED:
                    toggle_mode = "Taster (Einmal abspielen)"
                elif func_sound.toggle_mode == ToggleMode.SWITCH:
                    toggle_mode = "Umschalter"
                else:
                    toggle_mode = "Anschalter (bis Geräuschende)"
                self.liststore.append([func_sound.name,
                                       func_sound.file_path,
                                       state,
                                       func_sound.button,
                                       toggle_mode])
            self.set_cursor(Gtk.TreePath.new_from_string("0"))
        
    def save_changes(self, path, column_nr, new_value):
        if new_value == "An":
            new_value = True
        elif new_value == "Aus":
            new_value = False
        elif new_value == "Taster (Mehrmals abspielen)":
            new_value = ToggleMode.PUSH
        elif new_value == "Taster (Einmal abspielen)":
            new_value = ToggleMode.PUSH_LIMITED
        elif new_value == "Umschalter":
            new_value = ToggleMode.SWITCH
        elif new_value == "Anschalter (bis Geräuschende)":
            new_value = ToggleMode.TAP
        setattr(Config.active_loco.function_sounds[path.get_indices()[0]], Config.function_sound_attributes[column_nr][0], new_value)

class ControlPointGraph(Gtk.DrawingArea):
    width = 550 # minimum width + height
    height = 340
    border_left_bottom = 60.0 # important: border_left_bottom must be larger than radius_large + the width/height of the axes!
    border_right = 10
    coordinate_line_length = 7
    axis_distance = 2
    radius_small = 3.6
    radius_large = 7.3
    control_point_border_width = 1.3
    min_label_distance = 7
    drag = None
    line_color = (0.2, 0.2, 0.4)
    control_point_outer_color = (0.1686, 0.1686, 0.1686)
    control_point_inner_color = (0.804, 0.804, 0.757)
    point_color = (0.35, 0.35, 0.7216)
    axes_color = (0, 0, 0)
    legend_color = (0.1, 0.1, 0.1)
    
    def __init__(self, max_digits_number=100):
        Gtk.DrawingArea.__init__(self)
        self.connect("draw", self.draw)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.add_events(Gdk.EventMask.BUTTON1_MOTION_MASK)
        self.connect("motion-notify-event", self.motion)
        self.connect("button-press-event", self.button_pressed)
        self.connect("button-release-event", self.button_released)
        self.set_valign(Gtk.Align.FILL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_size_request(self.width, self.height)
        
        self.max_digits_number = max_digits_number
        self.popup = Gtk.Window.new(Gtk.WindowType.TOPLEVEL) # we dont use the special popup class since we dont need the replace-content-functionality
        self.popup.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)
        self.popup.set_opacity(0.65)
        self.popup.label = Gtk.Label.new("")
        self.popup.add(self.popup.label)
    
    def draw(self, area, cr):
        if hasattr(self, "func"):
            new_width = self.get_allocated_width()
            new_height = self.get_allocated_height()
            if new_width != self.width or new_height != self.height:
                self.width = new_width
                self.height = new_height
                self.calc_size_factors()
                self.create_coordinate_system()
            cr.set_source_surface(self.coordinate_system, 0, 0)        
            cr.paint()
            cr.set_line_width(2.2)
            
            cr.set_source_rgb(*self.point_color)
            for y in xrange(1, int(self.y_max)):
                x = self.func.get_x(y)
                if x != None:
                    x_abs, y_abs = self.get_abs_coords(x, y)
                    cr.arc(x_abs, y_abs, self.radius_small, 0, 2 * pi)
                    cr.fill()
            cr.stroke()
            for nr in xrange(len(self.func.control_points) - 1):
                x_abs_1, y_abs_1 = self.get_abs_coords(*self.func.control_points[nr])
                x_abs_2, y_abs_2 = self.get_abs_coords(*self.func.control_points[nr + 1])
                
                cr.move_to(x_abs_1, y_abs_1)
                cr.set_source_rgb(*self.line_color)
                cr.line_to(x_abs_2, y_abs_2)
                cr.stroke()
                
                cr.set_source_rgb(*self.control_point_outer_color)
                cr.arc(x_abs_1, y_abs_1, self.radius_large, 0, 2 * pi)
                cr.fill()
                cr.set_source_rgb(*self.control_point_inner_color)
                cr.arc(x_abs_1, y_abs_1, self.radius_large - self.control_point_border_width, 0, 2 * pi)
                cr.fill()
            
            cr.set_source_rgb(*self.control_point_outer_color)
            cr.arc(x_abs_2, y_abs_2, self.radius_large, 0, 2 * pi)
            cr.fill()
            cr.set_source_rgb(*self.control_point_inner_color)
            cr.arc(x_abs_2, y_abs_2, self.radius_large - self.control_point_border_width, 0, 2 * pi)
            cr.fill()
            cr.stroke()
    
    def get_touched_point(self, x, y):
        result = None, None
        for nr, point in enumerate(self.func.control_points):
            x_abs, y_abs = self.get_abs_coords(*point)
            circle_left_end = x_abs - self.radius_large
            circle_right_end = x_abs + self.radius_large
            circle_upper_end = y_abs - self.radius_large
            circle_lower_end = y_abs + self.radius_large
            if circle_left_end < x < circle_right_end and circle_upper_end < y < circle_lower_end:
                result = nr, point
                break
        return result
    
    def get_abs_coords(self, x, y):
        return self.border_left_bottom + x * self.x_factor, self.height - self.border_left_bottom - y * self.y_factor
    
    def get_speed_coords(self, x, y):
        return (x - self.border_left_bottom) / self.x_factor, (self.height - self.border_left_bottom - y) / self.y_factor
    
    def button_pressed(self, area, event):
        nr, point = self.get_touched_point(event.x, event.y)
        if nr != None:
            if event.button == 3:
                self.func.remove_control_point(nr)
                self.queue_draw()
                self.update_config_object()
            else:
                self.drag = nr
                self.popup.set_position(Gtk.WindowPosition.MOUSE)
                self.popup.label.set_text(str("%0.2f" % point[0]) + "\n" + str("%0.2f" % point[1]))
                self.popup.show_all()
        else:
            x, y = self.get_speed_coords(event.x, event.y)
            self.func.add_control_point(x, y)
            self.queue_draw()
            self.update_config_object()
            
    def update_config_object(self):
        Config.unsaved_changes(self.func, "control_points", self.func.control_points)
        Config.unsaved_changes(self.func, "func_segments", self.func.func_segments)
    
    def button_released(self, area, event):
        if self.drag != None:
            self.update_config_object()
            self.popup.hide()
            self.drag = None
    
    def motion(self, area, event):
        if self.drag != None:
            x, y = self.get_speed_coords(event.x, event.y)
            if x < 0:
                x = 0
            elif x > self.x_max:
                x = self.x_max
            if y < 0:
                y = 0
            elif y > self.y_max:
                y = self.y_max
            new_point = self.func.move_control_point(self.drag, x, y)
            self.queue_draw()
            self.popup.label.set_text(str("%0.2f" % new_point[0]) + "\n" + str("%0.2f" % new_point[1]))
                
    def create_coordinate_system(self):
        self.coordinate_system = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        c = cairo.Context(self.coordinate_system)
        c.set_line_width(2)
        c.select_font_face("sans-serif")
        c.set_font_size(14)
        c.set_source_rgb(*self.legend_color)
        
        x_res = self.get_resolution(20.0, self.x_max, self.x_res_list) 
        y_res = self.get_resolution(20.0, self.y_max, self.y_res_list)
        
        decimal_places_y_res = y_res - int(y_res)
        decimal_places_y_max = self.y_max - int(self.y_max)
        max_digits = float(max(decimal_places_y_res, decimal_places_y_max, key=lambda dec: len(str(dec)))) # calculate number with most digits
        if max_digits != 0:
            max_digits_number = int(self.y_max) + max_digits
        else:
            max_digits_number = int(self.y_max)
        max_width, height = c.text_extents(str(max_digits_number))[2:4] # calculate highest possible width of a number-label at y-axis
        
        x_axis_y_start = self.height - self.border_left_bottom + self.radius_large + self.axis_distance
        x_axis_y_end = self.height - self.border_left_bottom + self.radius_large + self.axis_distance + self.coordinate_line_length + height
        
        y_axis_x_start = self.border_left_bottom - self.radius_large - self.axis_distance - self.coordinate_line_length - max_width
        y_axis_x_end = self.border_left_bottom - self.radius_large - self.axis_distance
        
        x_legend_width, x_legend_height = c.text_extents(self.x_legend_text)[2:4]
        y_legend_width, y_legend_height = c.text_extents(self.y_legend_text)[2:4]
        
        c.move_to(0.5 * (self.width - self.border_left_bottom - x_legend_width), x_axis_y_end + 0.5 * (self.height - x_axis_y_end + x_legend_height))
        c.show_text(self.x_legend_text)

        c.move_to(0.5 * (y_axis_x_start + y_legend_height), 0.5 * (self.height - self.border_left_bottom + y_legend_width))
        c.rotate(pi / -2.0)
        c.show_text(self.y_legend_text)
        c.rotate(pi / 2.0)
        c.set_font_size(12)
        c.set_source_rgb(*self.axes_color)
        
        pos = 0
        used_width = 0
#        abs_x_max = self.get_abs_coords(self.x_max, 0)[0]
        while pos <= self.x_max + x_res:
            text, x, y, width, height = self.get_axis_data_at_pos(c, pos, x_res, self.x_max)
            if x > used_width + self.min_label_distance:
                c.move_to(x, x_axis_y_start)
                c.line_to(x, x_axis_y_end - height - 3)
                c.move_to(x - 0.5 * width, x_axis_y_end)
                c.show_text(text)
                used_width = x + width
            pos += x_res
        
        pos = 0
        used_height = self.height
        while pos <= self.y_max + y_res:
            text, x, y, width, height = self.get_axis_data_at_pos(c, pos, y_res, self.y_max)
            if y < used_height - self.min_label_distance:
                c.move_to(y_axis_x_start + max_width + 3, y)
                c.line_to(y_axis_x_end, y)
                c.move_to(y_axis_x_start, y + 0.5 * height)
                c.show_text(text)
                used_height = y - height
            pos += y_res
        c.stroke_preserve()
        
    def get_resolution(self, nr_labels, max_value, res_list):
        estimated_res = max_value / nr_labels
        for res in res_list:
            if res >= estimated_res:
                return res
        
    def get_axis_data_at_pos(self, c, pos, res, max_value):
        if pos >= max_value and pos - res != max_value:
            value = int(max_value) # FIXME: if float returned by Gtk.SpinButton is converted to int, the int has the wrong value
        else:
            value = int(pos)
        text = str(value)
        x, y = self.get_abs_coords(value, value)
        width, height = c.text_extents(text)[2:4]
        return text, x, y, width, height
    
    def calc_size_factors(self):
        self.x_factor = (self.width - self.border_left_bottom - self.radius_large - self.border_right) / float(self.x_max)
        self.y_factor = (self.height - self.border_left_bottom - self.radius_large) / float(self.y_max)
        
    def get_needed_space(self):
        return self.border_left_bottom, self.border_right + self.radius_large
    
    def clear(self):
        if hasattr(self, "func"): # all attribs must be set at once in get_func_data, so we only need to check if one of them exists
            del self.func
            del self.x_max
            del self.y_max
        self.queue_draw()
        
    def load(self, config_object):
        self.get_func_data(config_object)
        self.calc_size_factors()
        self.create_coordinate_system()
        self.queue_draw()

class SpeedStepGraph(ControlPointGraph):
    x_legend_text = "Geschwindigkeit in km/h"
    y_legend_text = "Fahrstufe"
    x_res_list = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2.5, 5, 10, 20, 50] # list of acceptable x-resolutions
    y_res_list = [1, 2, 10]
    
    def __init__(self):
        ControlPointGraph.__init__(self, 128)
    
    def get_func_data(self, loco):
        self.x_max = loco.max_speed
        self.y_max = loco.speed_steps
        self.func = loco.speed_to_step_func

class EngineDialog(Gtk.MessageDialog):
    sound_labels = {EngineType.DIESEL: "Verbrennungsmotor",
                    EngineType.STEAM: "Dampf",
                    None: "Kein Geräusch"}
    def __init__(self, engine_type, main_window):
        Gtk.MessageDialog.__init__(self,
                                   main_window,
                                   0,
                                   Gtk.MessageType.WARNING,
                                   Gtk.ButtonsType.NONE,
                                   "Durch Änderung des Geräuschmodells zu \"" + self.sound_labels[engine_type] + "\" werden die momentan festgelegten" +
                                   " Geräuschdateien zurückgesetzt!")
        self.add_buttons("Abbrechen", 0, "Geräuschmodell ändern", 1)
        
class SpeedSoundFrame(Gtk.Frame):
    loco_sound_bars = {}
    engine_attributes = {"diesel": ["start_sound", "idle_sound", "quit_sound"],
                       "steam": ["idle_sound", "cylinder_steam_sound", "nr_strokes", "stroke_start_delay", "wheel_diameter", "min_freq"]}
    engine_types = [(None, "Kein Geräusch"), ("steam", "Dampf"), ("diesel", "Verbrennungsmotor")] #, ("electro", "Elektrisch")]
    engine_type = "steam"
    loading = False
    inner_margin = 10
    
    def __init__(self, graph, main_window):
        Gtk.Frame.__init__(self)
        self.speed_graph = graph
        self.main_window = main_window
        self.grid = Gtk.Grid()
        
        self.engine_params_w_defs = {"diesel":
                            [("Start-Geräusch", "Geräusch für das Starten der Lokomotive", [EntryTableType.SOUND_FILE]),
                             ("Leerlaufgeräusch", "Geräusch im Leerlauf", [EntryTableType.SOUND_FILE]),
                             ("Abstellgeräusch", "Geräusch für das Herunterfahren / Abstellen der Lokomotive", [EntryTableType.SOUND_FILE]),
                             ("Geräusch-Ereignisse", "Wiedergabe von Geräuschdateien anhand bestimmter Ereignisse festlegen",
                               [EntryTableType.BUTTON, "Bearbeiten", self.edit_sounds])],
                            "steam":
                            [("Leerlaufgeräusch", "Geräusch im Leerlauf", [EntryTableType.SOUND_FILE]),
                             ("Dampfablass-Geräusch", "Geräusch beim Ausströmen von Dampf aus den Zylindern", [EntryTableType.SOUND_FILE]),
                             ("Takte", "Anzahl der Zylinder-Takte der Dampflok", [EntryTableType.INT]),
                             ("Dampfablass-Dauer", "Zeit in der Dampf aus den Zylindern strömt bevor die Lok anfährt in s", [EntryTableType.FLOAT]),
                             ("Treibrad-Durchmesser", "Durchmesser eines Antriebsrades in m", [EntryTableType.FLOAT, 0.001]),
                             ("Minimale Taktfrequenz", "Die kleinstmögliche Frequenz in Takten pro s", [EntryTableType.FLOAT, 0.01]),
                             ("Geräusch-Ereignisse",
                               "Wiedergabe von Geräuschdateien anhand bestimmter Ereignisse festlegen",
                               [EntryTableType.BUTTON, "Bearbeiten", self.edit_sounds])]
                            }
        
        liststore = Gtk.ListStore(GObject.TYPE_STRING)
        for engine_type, type_def in self.engine_types:
            liststore.append([type_def])
        self.type_combo = EasyComboBox(liststore, self.engine_types)
        self.type_combo.set_valign(Gtk.Align.START)
        self.type_combo.set_halign(Gtk.Align.START)
        self.type_combo.connect("changed", self.engine_type_changed)
        self.grid.add(self.type_combo)
        
        self.separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        self.separator.set_margin_left(self.inner_margin)
        self.separator.set_margin_right(self.inner_margin)
        self.separator.show()
        
        self.popup = Popup(main_window, "Geräusch-Ereignisse", Gdk.WindowTypeHint.DIALOG)
        self.event_sound_frame = EventSoundFrame(self.popup)
        self.popup.set_content(self.event_sound_frame)
        
        self.set_horizontal_margins()
        self.add(self.grid)        
        
    def load(self, loco): # the loco has changed -> update the type_combo + sound_options
        self.loading = True # prevent type_combos callback from being called when a new loco is loaded
        self.loco = loco
        self.remove_sound_options()
        if loco.engine != None:
            self.type_combo.set_value(loco.engine.type)
            self.create_sound_options()
            self.event_sound_frame.treeview.load(loco.engine.event_sounds)
        else:
            self.type_combo.set_value(None)
        self.loading = False
        
    def create_sound_options(self):
        self.table = EntryTable(self.engine_params_w_defs[self.loco.engine.type],
                                       self.engine_attributes[self.loco.engine.type],
                                       True,
                                       False,
                                       Gtk.Orientation.HORIZONTAL,
                                       3)
        self.table.set_halign(Gtk.Align.END)
        self.table.load(self.loco.engine)            
        self.table.show_all()
        self.grid.attach(self.table, 1, 0, 1, 1)
        
        # test if engine displayed in sound-bar is still the same as in loco (if not, new sound-bar is needed)
        if self.loco in self.loco_sound_bars and self.loco_sound_bars[self.loco].engine == self.loco.engine:
            self.sound_bar = self.loco_sound_bars[self.loco]
        else:
            self.sound_bar = SegmentedSoundBar(self.speed_graph, self, self.main_window)
            self.sound_bar.load(self.loco)
            self.sound_bar.set_horizontal_margins(self.inner_margin - 0.5 * self.sound_bar.handle_width)
            self.loco_sound_bars[self.loco] = self.sound_bar
        self.grid.attach_next_to(self.separator, self.type_combo, Gtk.PositionType.BOTTOM, 2, 1)
        self.grid.attach_next_to(self.sound_bar, self.separator, Gtk.PositionType.BOTTOM, 2, 1)
        
        
    def remove_sound_options(self):
        if self.separator.get_parent() != None:
            self.grid.remove(self.separator)
            self.grid.remove(self.sound_bar)
            self.grid.remove(self.table)
            del self.sound_bar
            
    def set_horizontal_margins(self):
        graph_margin_left, graph_margin_right = self.speed_graph.get_needed_space()
        border = self.get_style_context().get_border(Gtk.StateFlags.NORMAL)
        margin_left = graph_margin_left - self.inner_margin - border.left
        margin_right = graph_margin_right - self.inner_margin - border.right
        self.set_margin_left(margin_left)
        self.set_margin_right(margin_right)

    def engine_type_changed(self, combo): # the selected value of the engine-type-combo has changed -> update the loco and the sound-options
        if not self.loading: # prevent this from being called when a new loco is loaded -> we just want to display the locos engine type + don't change it
            new_engine_type = self.type_combo.retrieve_value()
            if self.loco.engine != None:
                engine_dialog = EngineDialog(new_engine_type, self.main_window)
                response = engine_dialog.run()
                engine_dialog.destroy()
            else:
                response = True
            if response:
                self.remove_sound_options()
                if new_engine_type != None:
                    engine = config.create_engine(new_engine_type, Config.unsaved_changes)
                    new_segment = config.create_sound_segment(engine.type,
                                                              Config.unsaved_changes,
                                                              0,
                                                              self.loco.max_speed)
                    new_segment.set_position(SegmentPosition.UPPER)
                    engine.sound_segments = [new_segment]
                    self.loco.engine = engine
                    self.create_sound_options()
                else:
                    self.loco.engine = None
            else:
                self.loading = True
                combo.set_value(self.loco.engine.type)
                self.loading = False
                
    def show_pause_graph(self, button):
        self.pause_graph_popup.show_at_center()
        
    def hide_pause_graph(self, button):
        self.pause_graph_popup.hide()
        
    def edit_sounds(self, button):
        self.popup.show_at_mouse()

class CustomHandlePaned(Gtk.Paned):
    def __init__(self):
        Gtk.Paned.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_name("custom-handle-paned")
        self.set_hexpand(True)
        self.set_size_request(-1, 30) # Attention: these values only fit to the shipped handle-icon!

class SegmentedSoundBar(Gtk.Grid):
    handle_width = 6 # has to fit the width set in gtk_styles_and_transitions.css
    
    def __init__(self, graph, speed_sound_grid, main_window):
        Gtk.Grid.__init__(self)
        self.graph = graph
        self.speed_sound_grid = speed_sound_grid
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.left_handle = Gtk.Image.new_from_file("./Icons/sound-bar-pane-handle3.png")
        self.left_handle.set_halign(Gtk.Align.START)
        self.right_handle = Gtk.Image.new_from_file("./Icons/sound-bar-pane-handle3.png")
        self.right_handle.set_halign(Gtk.Align.END)
        self.add(self.left_handle)
        self.add(self.right_handle)
        self.set_margin_top(5)
        self.popup = Popup(main_window)
        
        
    def load(self, loco):
        self.loco = loco # needed by SoundSelectorButton
        self.engine = loco.engine # needed for comparison with the current loco.engine in SpeedSoundFrame to find out if new soundbar is needed
        if hasattr(self, "paned"):
            self.remove(self.parent_paned)
            self.parent_paned.destroy()
        self.paned = CustomHandlePaned()
        self.parent_paned = self.paned
        self.insert_column(1)
        self.attach(self.paned, 1, 0, 1, 1)
        Config.notice_unsaved_changes = False # changing the position should not trigger unsaved_changes
        for segment in loco.engine.sound_segments[:-1]:
            segment.set_position(SegmentPosition.MIDDLE)
        loco.engine.sound_segments[-1].set_position(SegmentPosition.UPPER)
        Config.notice_unsaved_changes = True
        for nr, segment in enumerate(loco.engine.sound_segments):
            button = create_sound_selector_button(loco.engine.type, "Geräusch " + str(nr + 1), self.popup, segment, self)
            self.paned.pack1(button, False, False)
            max_width = self.graph.get_allocated_width() - self.graph.border_left_bottom - self.graph.border_right - self.handle_width            
            position = (segment.end - segment.start) / loco.max_speed * max_width - self.handle_width
            self.paned.set_position(position)
            self.paned.connect("button-release-event", self.sounds_changed)
            
            if nr < len(loco.engine.sound_segments) - 1:
                new_paned = CustomHandlePaned()
                self.paned.pack2(new_paned, False, False)
                self.paned = new_paned
        self.show_all()
        
    def sounds_changed(self, *args):
        paned = self.parent_paned
        nr_handles = len(self.loco.engine.sound_segments) - 1
        width = float(paned.get_allocated_width()) - nr_handles * self.handle_width
        start = 0
        for nr, segment in enumerate(self.loco.engine.sound_segments):
            child_width = float(paned.get_child1().get_allocated_width())
            segment.start = start / width * self.loco.max_speed
            segment.end = segment.start + child_width / width * self.loco.max_speed
            start += child_width
            paned = paned.get_child2()
            
    def set_horizontal_margins(self, margin):
        self.set_margin_left(margin)
        self.set_margin_right(margin)
        
class PopupButton(Gtk.Button):
    def __init__(self, text, use_bold, popup):
        Gtk.Button.__init__(self)
        if use_bold:
            label = BoldLabel(text)
        else:
            label = Gtk.Label.new(text)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        self.add(label)
        self.popup = popup
        self.connect("clicked", self.show_popup)
        
    def show_popup(self, button):
        self.popup.show_at_mouse()

def create_sound_selector_button(engine_type, *args):
    if engine_type == EngineType.DIESEL:
        return DieselSoundSelectorButton(*args)
    elif engine_type == EngineType.STEAM:
        return SteamSoundSelectorButton(*args)

class SoundSelectorButton(PopupButton):    
    def __init__(self, text, popup, segment, sound_bar):
        PopupButton.__init__(self, text, True, popup)
        self.grid = Gtk.Grid()
        
        delete_sound_button = StockImageButton("Geräusch löschen", Gtk.STOCK_DELETE)
        delete_sound_button.set_halign(Gtk.Align.START)
        delete_sound_button.connect("clicked", self.delete_sound)
        self.grid.attach(delete_sound_button, 0, 1, 1, 1)
        
        insert_sound_button = StockImageButton("Geräusch rechts einfügen", Gtk.STOCK_ADD)
        insert_sound_button.set_halign(Gtk.Align.END)
        insert_sound_button.connect("clicked", self.insert_sound)
        self.grid.attach(insert_sound_button, 1, 1, 1, 1)
        
        self.close_button = StockImageButton("Schließen", Gtk.STOCK_CLOSE)
        self.close_button.connect("clicked", self.hide_popup)
        self.close_button.set_halign(Gtk.Align.END)
        
        self.grid.attach(self.close_button, 1, 2, 1, 1)
        self.segment = segment
        self.sound_bar = sound_bar
        
    def set_content(self, content):
        if hasattr(self, "content"):
            self.grid.remove(self.content)
        self.content = content
        self.grid.attach(content, 0, 0, 2, 1)
        
    def delete_sound(self, button):
        loco = self.sound_bar.loco
        engine = loco.engine
        index = engine.sound_segments.index(self.segment)
        
        engine.sound_segments.remove(self.segment)
        if len(engine.sound_segments) > 0:
            prev_segment = engine.sound_segments[index - 1]
            prev_segment.end = self.segment.end
            if self.segment.position == SegmentPosition.UPPER:
                prev_segment.set_position(SegmentPosition.UPPER)
            self.sound_bar.load(loco)
            Config.unsaved_changes(loco.engine, "sound_segments", loco.engine.sound_segments)
        else:
            del self.sound_bar.speed_sound_grid.loco_sound_bars[loco]
            self.sound_bar.speed_sound_grid.type_combo.set_value(None) # type_combo will take care of setting loco.engine = None
        self.popup.hide()
        
    def insert_sound(self, button):
        sound_bar = self.sound_bar
        loco = self.sound_bar.loco
        sound_segments = loco.engine.sound_segments
        border = 0.5 * (self.segment.end + self.segment.start)
        if self.segment.position == SegmentPosition.UPPER: # if this segment is at the end, we need to insert a SegmentPosition.UPPER-segment
            self.segment.set_position(SegmentPosition.MIDDLE) # and replace this segment with middle-one
            new_segment = config.create_sound_segment(loco.engine.type,
                                                      Config.unsaved_changes,
                                                      border,
                                                      loco.max_speed)
            new_segment.set_position(SegmentPosition.UPPER)
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
        Config.unsaved_changes(loco.engine, "sound_segments", loco.engine.sound_segments)
        
    def hide_popup(self, button):
        self.popup.hide()
        
class DieselSoundSelectorButton(SoundSelectorButton):
    params_w_defs = [("Unter Last:", "Geräusch das im gewählten Geschwindigkeitsbereich\nunter Last abgespielt wird", [EntryTableType.SOUND_FILE]),
                     ("Im Leerlauf:", "Geräusch das im gewählten Geschwindigkeitsbereich\nim Leerlauf abgespielt wird", [EntryTableType.SOUND_FILE]),
                     ("Beschleunigungsvorgang:", "Beschleunigungsvorgang zu dieser Geräusch-Stufe", [EntryTableType.SOUND_FILE]),
                     ("Bremsvorgang:", "Bremsvorgang zur vorherigen Geräusch-Stufe", [EntryTableType.SOUND_FILE])]
    segment_attributes = ["load_sound", "idle_sound", "accel_sound", "decel_sound"]
    
    def __init__(self, text, popup, segment, sound_bar): # sound_bar
        SoundSelectorButton.__init__(self, text, popup, segment, sound_bar)
        if segment.position == SegmentPosition.UPPER:
            params_w_defs = self.params_w_defs[:1] + self.params_w_defs[2:]
            attributes = self.segment_attributes[:1] + self.segment_attributes[2:]
            self.table = EntryTable(params_w_defs, attributes, True, False)
        else:
            self.table = EntryTable(self.params_w_defs, self.segment_attributes, True, False)
        self.set_content(self.table)
        
    def show_popup(self, button): # override standard implementation (include loading)
        self.table.load(self.segment)
        self.popup.set_content(self.grid)
        self.popup.show_at_mouse()
        
class SteamSoundSelectorButton(SoundSelectorButton):    
    def __init__(self, text, popup, segment, sound_bar): # sound_bar
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
        for stroke_nr in xrange(self.sound_bar.loco.engine.nr_strokes):
            button = EasyFileButton([SoundFileFilter()])
            button.set_tooltip_text("Geräusch für Zylindertakt " + str(stroke_nr + 1))
            path = self.segment.stroke_sounds[stroke_nr]
            if path != None:
                button.set_value(path)
                
            button.connect("file-set", self.file_set, stroke_nr)
            label = Gtk.Label("Takt " + str(stroke_nr + 1))
            label.set_halign(Gtk.Align.CENTER)
            grid.attach(label, 0, stroke_nr, 1, 1)
            grid.attach(button, 1, stroke_nr, 1, 1)
            self.buttons.append(button)
        return grid
    
    def update_stroke_sounds(self):
        nr_strokes = self.sound_bar.loco.engine.nr_strokes
        if self.segment.stroke_sounds == None or len(self.segment.stroke_sounds) < nr_strokes:
            self.segment.stroke_sounds = [None for i in xrange(nr_strokes)]
        
    def show_popup(self, button):
        self.set_content(self.create_grid())
        self.popup.set_content(self.grid)
        self.popup.show_at_mouse()
        
    def file_set(self, button, stroke_nr):
        self.segment.stroke_sounds[stroke_nr] = button.retrieve_value()
        Config.unsaved_changes(self.segment, "stroke_sounds", self.segment.stroke_sounds)

class Popup(Gtk.Window):
    def __init__(self, main_window, title="", type_hint=Gdk.WindowTypeHint.TOOLTIP):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        self.set_title("ELECTRIP " + ELECTRIP_VERSION + " - " + title)
        self.connect("delete-event", self.delete_event)
        if type_hint != None:
            self.set_type_hint(type_hint)
        self.main_window = main_window
        
    def show_at_mouse(self):
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.set_transient_for(self.main_window)
        self.show_all()
        
    def show_at_center(self):
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_transient_for(self.main_window)
        self.show_all()
        
    def set_content(self, widget): # can be called multiple times
        if hasattr(self, "content"):
            self.remove(self.content)
        self.resize_to_geometry(1, 1)
        self.content = widget
        self.add(self.content)
        
    def delete_event(self, window, event):
        self.hide()
        return True
