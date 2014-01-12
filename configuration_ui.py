#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository import GObject, Gtk, Pango, Gdk
from os.path import normpath
import cairo
import config
from math import pi
from constants import ELECTRIP_VERSION, PROTOCOLS, RELOAD_GRAPH_IMAGE_PATH
from electrip import StockImageButton
from dialog_templates import ImageFileFilter, AllFileFilter, SoundFileFilter, \
    WarningDialog
from locked_print import locked_print
import dialog_templates
from zipfile import BadZipfile

class MainBox(Gtk.Notebook):
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

        self.loco_scrolled_window = ScrolledTreeView(LocoTreeView(self.loco_properties_frame,
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
        
        horizontal_grid = Gtk.Grid()
        horizontal_grid.add(self.loco_grid)
        horizontal_grid.add(self.scrolled_window_loco_properties)
        horizontal_grid.add(Gtk.Separator.new(Gtk.Orientation.VERTICAL))
        self.append_page(horizontal_grid, Gtk.Label("Lokomotiven"))
        
        self.server_table = ServerTable()
        self.append_page(TopAlignment(self.server_table),
                         Gtk.Label("SRCP-Server"))
        
        self.joystick_table = JoystickTable()
        self.append_page(TopAlignment(self.joystick_table),
                         Gtk.Label("Gamepad"))
        
        self.sound_table = SoundTable()
        self.append_page(TopAlignment(self.sound_table),
                         Gtk.Label("Geräusch"))
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
        self.set_border_width(6)
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
        TreeViewFrame.__init__(self,
                               "Funktionen",
                               self.treeview,
                               self.action_box)
        self.set_sensitive(False)
        
class EventSoundFrame(TreeViewFrame):
    def __init__(self, popup):
        self.treeview = EventSoundTreeView(popup)
        self.action_box = EventSoundActionBox(self.treeview)
        TreeViewFrame.__init__(self,
                               "Geräusch-Ereignisse",
                               self.treeview,
                               self.action_box)
        
class FunctionSoundFrame(TreeViewFrame):
    def __init__(self, popup):
        self.treeview = FunctionSoundTreeView(popup)
        self.action_box = FunctionSoundActionBox(self.treeview)
        TreeViewFrame.__init__(self,
                               "Geräusch-Funktionen",
                               self.treeview,
                               self.action_box)

# is in fact an overlay, but uses a frame as "background"
class SpeedGraphFrame(Gtk.Overlay):
    loco_sound_bars = {}
    warn_frame_active = False
    
    def __init__(self, main_window):
        Gtk.Overlay.__init__(self)
        frame = Frame("Geschwindigkeitsverlauf")
        self.graph = SpeedStepGraph()
        self.speed_sound_frame = SpeedSoundFrame(self.graph, main_window)
        self.cancel_button = StockImageButton("Abbrechen", Gtk.STOCK_CANCEL)
        self.cancel_button.connect("clicked", self.change_axis, False)
        self.accept_button = StockImageButton("Zurücksetzen", Gtk.STOCK_OK)
        self.accept_button.connect("clicked", self.change_axis, True)
        self.warn_image = Gtk.Image.new_from_file(RELOAD_GRAPH_IMAGE_PATH)
        self.warn_image.set_margin_right(7)
        self.warn_label = Gtk.Label()
        self.warn_label.set_vexpand(True)
        
        self.warn_frame = Frame("Kennlinie zurücksetzen?")
        warn_grid = Gtk.Grid()
        warn_grid.set_column_spacing(11)
        warn_grid.set_row_spacing(11)
        warn_grid.set_halign(Gtk.Align.CENTER)
        warn_grid.set_valign(Gtk.Align.CENTER)
        warn_grid.attach(self.warn_image, 0, 0, 1, 2)
        warn_grid.attach(self.warn_label, 1, 0, 2, 1)
        warn_grid.attach(self.cancel_button, 1, 1, 1, 1)
        warn_grid.attach(self.accept_button, 2, 1, 1, 1)
        self.warn_frame.add(warn_grid)
        self.warn_frame.show_all()
        
        self.grid = Gtk.Grid()
        self.grid.set_orientation(Gtk.Orientation.VERTICAL)
        self.grid.set_row_spacing(5)
        self.grid.add(self.speed_sound_frame)
        self.grid.add(self.graph)
        
        frame.add(self.grid)
        self.add(frame)
        self.set_sensitive(False)
        
    def confirm_axis_change(self,
                            message,
                            accept_callback,
                            undo_callback):
        self.warn_label.set_text(message)
        self.accept_callback = accept_callback
        self.undo_callback = undo_callback
        if not self.warn_frame_active:
            self.add_overlay(self.warn_frame)
            self.warn_frame_active = True
    
    def change_axis(self, button, accept_changes):
        if accept_changes:
            self.accept_callback()
            func = self.loco.speed_to_step_func
            func.load([(0.0, 0.0),
                       (float(self.loco.max_speed),
                        float(self.loco.speed_steps))])
            self.graph.load(self.loco)
            if self.loco.engine != None:
                self.speed_sound_frame.sound_bar.sounds_changed()
        else:
            self.undo_callback()
        self.remove(self.warn_frame)
        self.warn_frame_active = False
    
    def load(self, loco):
        self.loco = loco
        self.graph.load(loco)
        self.speed_sound_frame.load(loco)

class LoadLocoButton(Gtk.Button):
    def __init__(self, main_window, loco_treeview):
        Gtk.Button.__init__(self, "Lok laden")
        self.set_valign(Gtk.Align.END)
        self.connect("clicked",
                     self.import_loco,
                     main_window,
                     loco_treeview)
        
    def import_loco(self, button, main_window, loco_treeview):
        file_chooser_dialog = dialog_templates.LocoLoadDialog(main_window)
        response = file_chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            file_path = file_chooser_dialog.get_filename()
            try:
                Config.locos.append(Config.load_loco(file_path))
                loco_treeview.load()
            except IOError:
                main_window.error_dialog("Ein Dateipfad ist ungültig! "
                                         "Konnte Lok nicht importieren.")
            except KeyError:
                main_window.error_dialog("Ein Parameter konnte nicht geladen werden! "
                                         "Konnte Lok nicht importieren.")
            except BadZipfile:
                main_window.error_dialog("Die *.zip-Datei ist fehlerhaft! "
                                         "Konnte Lok nicht importieren.")
            except Exception as e:
                main_window.error_dialog("Ein unvorhergesehener Fehler "
                                         "trat auf:\n" + str(e))
        file_chooser_dialog.destroy()

class SaveLocoButton(Gtk.Button):
    def __init__(self, main_window):
        Gtk.Button.__init__(self, "Lok speichern")
        self.set_valign(Gtk.Align.END)
        self.connect("clicked", self.export_loco, main_window)
        
    def export_loco(self, button, main_window):
        if Config.active_loco != None:
            file_chooser_dialog = dialog_templates.LocoSaveDialog(main_window)
            response = file_chooser_dialog.run()
            if response == Gtk.ResponseType.OK:
                file_path = file_chooser_dialog.get_filename()
                Config.save_loco(Config.active_loco, file_path)
            file_chooser_dialog.destroy()

class LocoPropertiesFrame(Frame):
    def __init__(self, speed_graph_frame, main_window):
        Frame.__init__(self, "Allgemeine Eigenschaften")
        self.speed_graph_frame = speed_graph_frame
        
        self.table = EntryTable(True, False)
        self.table.add_float_entry("Höchstgeschwindigkeit",
                                   "Die reale Höchstgeschwindigkeit der Lokomotive in km/h",
                                   "max_speed",
                                   1.0, 999.0, 0.1)
        self.table.add_float_entry("Beschleunigungsdauer",
                                   "Zeit in s für die Beschleunigung von 0 "
                                   "auf Höchstgeschw. bei voller Auslenkung des Gamepads",
                                   "accel_duration",
                                   1.0, 9999.0, 0.1)
        self.table.add_float_entry("Bremsdauer",
                                   "Zeit in s für den Bremsvorgang von Höchstgeschw. "
                                   "auf 0 bei voller Auslenkung des Gamepads",
                                   "decel_duration",
                                   1.0, 9999.0, 0.1)
        self.table.add_combo_entry("Fahrtrichtung",
                                   "Voreingestellte Fahrtrichtung der Lokomotive",
                                   "direction",
                                   GObject.TYPE_STRING,
                                   ((True, "Vorwärts"),
                                    (False, "Rückwärts")))
        self.table.add_image_file_entry("Bild",
                                        "Pfad an dem das passende Lokbild abgelegt ist",
                                        "img_path")
        self.table.add_action_button("Geräusch-Funktionen",
                                     "Wiedergabe von Geräuschdateien als "
                                     "Lok-Funktionen konfigurieren",
                                     "Bearbeiten",
                                     self.edit_sounds)
        self.table.add_volume_entry("Lautstärke",
                                    "Lautstärke der Lokomotive",
                                    "sound_volume")
        
        self.table.entry_widgets[0].connect("value-changed", self.confirm_axis_change)
        self.add(self.table)
        self.set_sensitive(False)
        self.popup = Popup(main_window, "Geräusch-Funktionen", Gdk.WindowTypeHint.NORMAL)
        self.function_sound_frame = FunctionSoundFrame(self.popup)
        self.popup.set_content(self.function_sound_frame)

    def load(self, loco):
        self.loading = True
        self.table.load(loco)
        self.function_sound_frame.treeview.load(loco.function_sounds)
        self.loading = False
        
    def edit_sounds(self, button):
        self.popup.show_at_mouse()
        
    def confirm_axis_change(self, entry):
        if not self.loading:
            self.speed_graph_frame.confirm_axis_change("Durch die Änderung der "
                                                       "Höchstgeschwindigkeit zu " +
                                                       str(entry.retrieve_value()) +
                                                       "\nwird die Geschwindigkeitskennlinie "
                                                       "zurückgesetzt!",
                                                       self.confirm_max_speed,
                                                       self.reset_max_speed)
        else:
            self.confirm_max_speed()
        
    def confirm_max_speed(self):
        self.stored_max_speed = self.table.entry_widgets[0].retrieve_value()
    
    def reset_max_speed(self):
        self.table.entry_widgets[0].set_value(self.stored_max_speed)

class DecoderFrame(Frame):
    def __init__(self, speed_graph_frame, main_window):
        Frame.__init__(self, "Digitaldecoder")
        self.table = DecoderTable(speed_graph_frame, main_window)
        self.add(self.table)
        self.set_sensitive(False)
        
    def load(self, loco):
        self.table.load(loco)

class ArrowButton(Gtk.Button):
    def __init__(self, direction): # direction: True = nach oben
        Gtk.Button.__init__(self)
        if direction:
            self.set_image(Gtk.Arrow.new(Gtk.ArrowType.UP,
                                         Gtk.ShadowType.NONE))
        else:
            self.set_image(Gtk.Arrow.new(Gtk.ArrowType.DOWN,
                                         Gtk.ShadowType.NONE))

class ScrolledTreeView(Gtk.ScrolledWindow):
    def __init__(self, treeview):
        Gtk.ScrolledWindow.__init__(self)
        self.set_policy(Gtk.PolicyType.AUTOMATIC,
                        Gtk.PolicyType.AUTOMATIC)
        self.treeview = treeview
        natural_req = self.treeview.get_preferred_size()[1]
        self.set_size_request(natural_req.width,
                              natural_req.height + 40)
        self.add(self.treeview)

class ActionBox(Gtk.ButtonBox):
    def __init__(self, treeview, add_row_label, remove_row_label):
        Gtk.ButtonBox.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_layout(Gtk.ButtonBoxStyle.START)
        self.add_row_button = Gtk.Button(add_row_label)
        
        # method add_row must be implemented in subclass
        self.add_row_button.connect("clicked",
                                    self.add_row, treeview)
        self.remove_row_button = Gtk.Button(remove_row_label)
        
        # method remove_row must be implemented in subclass
        self.remove_row_button.connect("clicked",
                                       self.remove_row, treeview)
        
        self.move_up_button = ArrowButton(True)
        self.move_up_button.connect("clicked",
                                    self.move_row,
                                    treeview,
                                    True)
        self.move_down_button = ArrowButton(False)
        self.move_down_button.connect("clicked",
                                      self.move_row,
                                      treeview,
                                      False)
        
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
                self.unsaved_changes()
            elif not direction and row_nr < len(liststore) - 1:
                self.move_row_down(row_nr)
                following_row = liststore.iter_nth_child(None, row_nr + 1)
                liststore.move_after(row, following_row)
                self.unsaved_changes()
            else:
                locked_print("Zeile befindet sich schon am Rand, "
                             "kann nicht weiter verschoben werden.")
        else:
            locked_print("Es ist keine Zeile ausgewählt, "
                         "es kann nichts verschoben werden.")
                
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
            locked_print("TreeView ist leer, es kann "
                         "nichts hinzugefügt werden.")
            
    def remove_row(self, button, treeview):
        path = treeview.get_cursor()[0]
        liststore = treeview.get_model()
        if path != None:
            self.remove_row_at(path.get_indices()[0])
            liststore.remove(liststore.get_iter(path))
            self.unsaved_changes()
        else:
            locked_print("Keine Zeile ausgewählt, "
                         "es kann nichts gelöscht werden.")

class LocoActionBox(ActionBox):
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
        ActionBox.__init__(self,
                           loco_treeview,
                           "Neue Lok",
                           "Lok löschen")
        
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

class FunctionActionBox(ActionBox):
    def __init__(self, function_treeview):
        ActionBox.__init__(self,
                           function_treeview,
                           "Neue Funktion",
                           "Funktion löschen")
        
    def get_liststore_row(self, function):
        return [function.name,
                function.nr,
                "Aus",
                function.button,
                "Umschalter"]
        
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
        
class EventSoundActionBox(ActionBox):    
    def __init__(self, event_sound_treeview):
        ActionBox.__init__(self,
                           event_sound_treeview,
                           "Neues Geräusch",
                           "Geräusch löschen")
        
    def get_liststore_row(self, event_sound):
        return [event_sound.name,
                event_sound.file_path,
                "An", "Egal", "Egal",
                "Egal", "Egal",
                event_sound.button]
        
    def add_row_at_start(self):
        new_event_sound = config.EventSound(Config.unsaved_changes)
        Config.active_loco.engine.event_sounds.append(new_event_sound)
        return self.get_liststore_row(new_event_sound)
    
    def add_row_beneath(self, row_nr):
        new_event_sound = config.EventSound(Config.unsaved_changes)
        Config.active_loco.engine.event_sounds.insert(row_nr + 1,
                                                      new_event_sound)
        return self.get_liststore_row(new_event_sound)
    
    def remove_row_at(self, row_nr):
        Config.active_loco.engine.event_sounds.pop(row_nr)
    
    def move_row_up(self, row_nr):
        Config.active_loco.engine.event_sounds.insert(row_nr - 1,
                                                      Config.active_loco.engine.event_sounds.pop(row_nr))
    
    def move_row_down(self, row_nr):
        Config.active_loco.engine.event_sounds.insert(row_nr + 1,
                                                      Config.active_loco.engine.event_sounds.pop(row_nr))
        
    def unsaved_changes(self):
        Config.unsaved_changes(Config.active_loco.engine,
                               "event_sounds",
                               Config.active_loco.engine.event_sounds)
        
class FunctionSoundActionBox(ActionBox):    
    def __init__(self, event_sound_treeview):
        ActionBox.__init__(self,
                           event_sound_treeview,
                           "Neues Geräusch",
                           "Geräusch löschen")
        
    def get_liststore_row(self, func_sound):
        return [func_sound.name,
                func_sound.file_path,
                "Aus",
                func_sound.button,
                "Anschalter (bis Geräuschende)"]
        
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

# subclassed combobox with methods allowing to
# easily acces the displayed value
class EasyComboBox(Gtk.ComboBox):
    # displayed_to_saved_vals: the names of the parameters
    # of config_object (often shorter than the displayed ones)
    # howto use: displayed_to_saved_vals =  [(parameter_name1,
    #                                         displayed_value1),
    #                                        (parameter_name2 ...
    def __init__(self, liststore, displayed_to_saved_vals): 
        Gtk.ComboBox.__init__(self)
        self.displayed_to_saved_vals = displayed_to_saved_vals
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
            
    def retrieve_disp_value(self):
        return self.get_model()[self.get_active()][0]
        
    def set_value(self, saved_value):
        saved_value_correct = False
        for saved_val, disp_val in self.displayed_to_saved_vals:
            if saved_value == saved_val:
                for row_nr, row in enumerate(self.get_model()):
                    if disp_val in row:
                        self.set_active(row_nr)
                        saved_value_correct = True
                        break
                break
        if not saved_value_correct:
            self.set_active(0)
            value = self.retrieve_value()
            locked_print("Dateiformat inkorrekt: Unbekannter Wert '" +
                         str(saved_value) +
                         "', verwende Standardwert '" +
                         str(value) + "'")
            self.emit("changed")

class EasyFileButton(Gtk.FileChooserButton):
    def __init__(self, file_filters=[]):
        Gtk.FileChooserButton.__init__(self, Gtk.FileChooserAction.OPEN)
        # the first file_filter is the active one
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
            # TODO: find out how to reset the filename to "None"
            self.set_filename("(keine)")
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
                 use_tooltips,
                 use_bold_params,
                 orientation=Gtk.Orientation.VERTICAL,
                 end=None):
        Gtk.Grid.__init__(self)
        
        self.set_column_spacing(10)
        self.set_row_spacing(5)
        self.set_border_width(6)
        
        self.use_tooltips = use_tooltips
        self.use_bold_params = use_bold_params
        self.orientation = orientation
        self.end = end
        
        # coordinates representing the position where
        # the next widget will be placed
        self.x = 0
        self.y = 0
        
        self.entry_widgets = []
        self.config_attributes = []
        
    def attach_entry_widget(self,
                            entry_widget,
                            label,
                            description,
                            config_attribute=None):
        if self.use_bold_params:
            parameter_label = BoldLabel(label)
        else:
            parameter_label = Gtk.Label(label)
        self.attach(parameter_label, self.x, self.y, 1, 1)
            
        if self.use_tooltips:
            entry_widget.set_tooltip_text(description)
        else:
            definition_label = Gtk.Label(label=description)
            definition_label.set_alignment(0, 0.5)
            self.attach(definition_label, self.x + 2, self.y, 1, 1)
        
        self.attach(entry_widget, self.x + 1, self.y, 1, 1)
        self.entry_widgets.append(entry_widget)
        self.config_attributes.append(config_attribute)
        
        # calculate the position for the next widget
        if self.orientation == Gtk.Orientation.VERTICAL:
            if self.end == None:
                self.y += 1
            else:
                if self.y < self.end - 1:
                    self.y += 1
                else:
                    self.x += 2
                    self.y = 0
        else:
            if self.end == None:
                self.x += 2
            else:
                if self.x < 2 * self.end - 2:
                    self.x += 2
                else:
                    self.y += 1
                    self.x = 0
                    
    def add_string_entry(self, label, description, config_attribute):
        """
        Adds a Gtk.Entry to the EntryTable.
        """
        entry = Gtk.Entry()
        entry.retrieve_value = entry.get_text
        entry.set_value = entry.set_text
        entry.connect("changed",
                      self.save_changes,
                      config_attribute)
        self.attach_entry_widget(entry, label, description, config_attribute)
        
    def add_int_entry(self,
                      label,
                      description,
                      config_attribute,
                      min_value=0,
                      max_value=9999,
                      step=1):
        """
        Adds a Gtk.SpinButton for integers to the EntryTable.
        
        Args:
            min_value: the minimal value of the int
            max_value: the maximal value of the int
            step: precision of the number as step
                between two possible values
        """
        spin_button = Gtk.SpinButton.new_with_range(min_value,
                                                    max_value,
                                                    step)
        spin_button.retrieve_value = spin_button.get_value_as_int
        spin_button.connect("value-changed",
                            self.save_changes,
                            config_attribute)
        self.attach_entry_widget(spin_button, label, description, config_attribute)
        
    def add_float_entry(self,
                        label,
                        description,
                        config_attribute,
                        min_value=0.0,
                        max_value=9999.0,
                        step=0.1):
        """
        Adds a Gtk.SpinButton for integers to the EntryTable.
        
        Args:
            min_value: the minimal value of the float
            max_value: the maximal value of the float
            step: precision of the float as step
                between two possible values
        """
        spin_button = Gtk.SpinButton.new_with_range(min_value,
                                                    max_value,
                                                    step)
        spin_button.retrieve_value = spin_button.get_value
        spin_button.connect("value-changed",
                            self.save_changes,
                            config_attribute)
        self.attach_entry_widget(spin_button, label, description, config_attribute)
        
    
    def add_combo_entry(self,
                        label,
                        description,
                        config_attribute,
                        content_type,
                        mapping):
        """
        Adds a Gtk.ComboBox to the EntryTable.
        
        Args:
            content_type: the type of the values
                to be stored in the combobox
                (e.g. str, float ...)
            mapping: list of 2-tuples, mapping values stored
                in the  model to the displayed values
        """
        liststore = Gtk.ListStore(content_type)
        for unused_saved_val, disp_val in mapping:
            liststore.append([disp_val])
        combo = EasyComboBox(liststore, mapping)
        combo.connect("changed",
                      self.save_changes,
                      config_attribute)
        self.attach_entry_widget(combo, label, description, config_attribute)
        
    def add_sound_file_entry(self, label, description, config_attribute):
        """
        Adds a Button for sound-file selection 
        to the EntryTable.
        """
        file_button = EasyFileButton([SoundFileFilter(), AllFileFilter()])
        file_button.connect("file-set",
                            self.save_changes,
                            config_attribute)
        self.attach_entry_widget(file_button, label, description, config_attribute)
        
    def add_image_file_entry(self, label, description, config_attribute):
        """
        Adds a Button for image-file selection 
        to the EntryTable.
        """
        file_button = EasyFileButton([ImageFileFilter(),
                                      AllFileFilter()])
        file_button.connect("file-set",
                            self.save_changes,
                            config_attribute)
        self.attach_entry_widget(file_button, label, description, config_attribute)
        
    def add_bool_entry(self, label, description, config_attribute):
        """
        Adds a Gtk.CheckButton for boolean values
        to the EntryTable.
        """
        check_button = Gtk.CheckButton()
        check_button.retrieve_value = check_button.get_active
        check_button.set_value = check_button.set_active
        check_button.connect("toggled",
                            self.save_changes,
                            config_attribute)
        self.attach_entry_widget(check_button, label, description, config_attribute)
        
    def add_volume_entry(self, label, description, config_attribute):
        """
        Adds a VolumeButton to the EntryTable.
        """
        volume_button = EasyVolumeButton()
        volume_button.connect("volume-set",
                              self.save_changes,
                              config_attribute)
        self.attach_entry_widget(volume_button, label, description, config_attribute)
        
    def add_action_button(self,
                          label,
                          description,
                          button_label,
                          callback):
        """
        Adds a Button with 'button_label' to the
        EntryTable which calls 'callback' when clicked.
        """
        button = Gtk.Button(button_label)
        button.connect("clicked", callback)
        self.attach_entry_widget(button, label, description)
        
    def add_label(self, label, description, markup):
        """
        Adds a Label with a text according to 'markup' to the
        EntryTable.
        """
        label_widget = Gtk.Label()
        label_widget.set_markup(markup)
        self.attach_entry_widget(label_widget, label, description)
            
    def load(self, config_object):
        self.config_object = config_object
        for nr, config_attribute in enumerate(self.config_attributes):
            if config_attribute != None:
                try:
                    value = getattr(config_object, config_attribute)
                except AttributeError:
                    locked_print("Attribut",
                                 config_attribute,
                                 "konnte nicht gefunden werden, "
                                 "es handelt sich evtl. um eine "
                                 "veraltete Electrip-Datei.")
                else:
                    self.entry_widgets[nr].set_value(value)
            
    def save_changes(self, widget, config_attrib):
        if config_attrib != None:
            value = widget.retrieve_value()
            # only set attributes when they differ from what is already saved
            # -> prevent signal-handler trouble on loading
            if getattr(self.config_object, config_attrib) != value:
                setattr(self.config_object, config_attrib, value)

class DecoderTable(EntryTable):
    restoring_speed_steps = False
    restoring_protocol = False
    
    def __init__(self, speed_graph_frame, main_window):
        EntryTable.__init__(self, True, False)
        self.add_combo_entry("Protokoll",
                             "Digitalprotokoll des Decoders",
                             "protocol",
                             GObject.TYPE_STRING,
                             (("M 1", "Märklin Motorola Version 1"),
                              ("M 2", "Märklin Motorola Version 2"),
                              ("N 1", "DCC kurzes Adressformat"),
                              ("N 2", "DCC langes Adressformat")))
        
        self.add_int_entry("Adresse",
                           "Adresse des Decoders",
                           "address", 1, 10239, 1)
        
        self.add_combo_entry("Fahrstufen",
                             "Anzahl Fahrstufen die der Decoder unterstützt",
                             "speed_steps",
                             GObject.TYPE_INT,
                             ((14, 14),))
        
        self.add_label("Funktionen",
                       "Maximale Anzahl Funktionen die "
                       "das Protokoll unterstützt",
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
        EntryTable.load(self, loco)
        self.loading = False
        
    def address_changed(self, entry):
        self.stored_address = entry.retrieve_value()
        
    def speed_steps_changed(self, combo):
        if not self.loading and not self.restoring_speed_steps:
            self.speed_graph_frame.confirm_axis_change("Durch Änderung der Anzahl Fahrstufen zu " +
                                                       str(combo.retrieve_value()) + \
                                                       "\nwird die Geschwindigkeitskennlinie "
                                                       "zurückgesetzt!",
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
                self.speed_graph_frame.confirm_axis_change("Durch die Änderung des Protokolls zu \"" +
                                                           combo.retrieve_disp_value() + "\" wird\n" + \
                                                           "- die Anzahl Fahrstufen auf " +
                                                           str(protocol_options[2][-1]) +
                                                           " gesetzt\n" + "- der Adressraum auf 1-" +
                                                           str(protocol_options[0]) + " beschränkt\n" + \
                                                           "Dadurch wird die "
                                                           "Geschwindigkeitskennlinie zurückgesetzt!",
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
        self.speed_steps_combo.displayed_to_saved_vals = disp_to_saved_vals
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

class ServerTable(EntryTable):
    def __init__(self):
        EntryTable.__init__(self, False, True)
        self.add_string_entry("Host", "IP-Adresse des Servers", "host")
        self.add_int_entry("Port",
                           "Port unter dem der Server erreichbar ist",
                           "port")
        self.add_int_entry("Bus",
                           "Bus auf dem Steuerungsbefehle gesendet werden sollen",
                           "bus")
        self.add_bool_entry("Strom",
                            "Strom beim Starten der Steuerung einschalten",
                            "power")
        self.load(Config.server)

class JoystickTable(EntryTable):
    def __init__(self):
        EntryTable.__init__(self, False, True)
        self.add_int_entry("Nothalt",
                           "Button am Gamepad über den die "
                           "Gleisspannung ausgeschaltet werden kann",
                           "emergency_button")
        self.add_int_entry("Richtungswender",
                           "Button am Gamepad für Richtungswechsel",
                           "reverse_button")
        self.add_int_entry("Beschleunigung",
                           "Achse am Gamepad für Geschwindigkeitsregelung",
                           "accel_axis")
        self.add_float_entry("Achsen-Schwellwert",
                             "Alle Achsen-Auslenkungswerte unter "
                             "diesem Toleranzwert werden ignoriert",
                             "axis_threshold",
                             0, 0.75, 0.01)
        self.add_int_entry("Fokus",
                           "Button am Gamepad, der die zurzeit "
                           "ausgewählte Lok in den im Fenster "
                           "sichtbaren Bereich holt",
                           "focus_button")
        self.add_int_entry("Geräusch",
                           "Button am Gamepad zum Ein-"
                           "/Ausschalten des Lok-Geräuschs",
                           "sound_button")
        self.add_bool_entry("Auto-Fokus",
                            "Ausgewählte Lok immer fokussieren "
                            "wenn nur ein Gamepad angeschlossen ist",
                            "use_auto_focus")
        self.add_bool_entry("Button-Nr",
                            "Nummer des zugehörigen Gamepad-Buttons "
                            "auf den Funktions-Buttons anzeigen",
                            "show_function_nr")
        self.load(Config.joystick)
        
class SoundTable(EntryTable):
    def __init__(self):
        EntryTable.__init__(self, False, True)
        self.add_combo_entry("Abtastrate",
                             "Die Abtastrate (Sampling Rate) der "
                             "verwendeten Geräuschdateien",
                             "sampling_rate",
                             GObject.TYPE_INT,
                             ((44800, 44800),
                              (44100, 44100),
                              (22050, 22050)))
        self.add_bool_entry("Geräuschlevel",
                            "Balken für das momentane Geräuschlevel "
                            "im Geschwindigkeitsregler anzeigen",
                            "show_level_bar")
        self.load(Config.sound)

# Base-class for TreeViews
class TreeView(Gtk.TreeView):
    """
    A simplified TreeView, allowing to easily add columns
    and keep them in sync with the 'config_object',
    which stores the configuration.
    """
    def __init__(self, name):
        """
        Args:
            name: The name of the TreeView, used for the
                'unsaved-changes'-messages
        """
        Gtk.TreeView.__init__(self)
        self.name = name
        
        # specifies the nr of columns the treeview currently has
        self.nr_columns = 0
        # lists the content-types for the columns 
        # (GObject.TYPE_xxx), according to their
        # 'colnr'-attribute
        self.column_types = []
    
    def add_column(self,
                   column_name,
                   column_tooltip,
                   cell_renderer,
                   content_type):
        """
        Adds a new column using 'cell_renderer'.
        """
        # Create a label with markup
        label = Gtk.Label()
        label.set_markup(column_name)
        label.set_tooltip_text(column_tooltip)
        label.show()
        # Create the column
        column = Gtk.TreeViewColumn(None, cell_renderer, text=self.nr_columns)
        column.set_widget(label)
        column.set_resizable(True)
        # Add a column-nr for easy identification
        column.colnr = self.nr_columns
        self.append_column(column)
        self.nr_columns += 1
        self.column_types.append(content_type)
        
    def update_model(self):
        """
        Overwrites the old liststore (if there is any) with the current
        column-setup. Must be called after all columns have been added.
        """
        self.liststore = Gtk.ListStore(*self.column_types)
        self.set_model(self.liststore)
    
    def add_text_colum(self,
                       column_name,
                       column_tooltip,
                       content_type):
        """
        Adds a column with editable text to the TreeView.
        
        Args:
            column_name: the column name (displayed above
                the column)
            column_tooltip: the tooltip for the column when
                the mouse hovers over it
        """
        text_renderer = Gtk.CellRendererText()
        text_renderer.set_property("editable", True)
        text_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        text_renderer.connect("edited", self.new_value)
        self.add_column(column_name,
                        column_tooltip,
                        text_renderer,
                        content_type)
        
    def add_non_editable_text_colum(self,
                                    column_name,
                                    column_tooltip,
                                    content_type):
        """
        Adds a column with non-editable text to the TreeView.
        
        Args:
            column_name: s. add_text_column
            column_tooltip: s. add_text_column
        """
        text_renderer = Gtk.CellRendererText()
        text_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        self.add_column(column_name,
                        column_tooltip,
                        text_renderer,
                        content_type)
        
    def add_combo_colum(self,
                        column_name,
                        column_tooltip,
                        content_type,
                        values):
        """
        Adds a column with 'ComboBox'es to the TreeView.
        
        Args:
            column_name: s. add_text_column
            column_tooltip: s. add_text_column
            content_type: the type of the values
                to be stored in the combobox
                (e.g. str, float ...)
            values: list of the values the user can
                choose from
        """
        combo_renderer = Gtk.CellRendererCombo()
        combo_renderer.set_property("editable", True)
        combo_renderer.set_property("has-entry", False)
        combo_renderer.set_property("text-column", 0)
        combo_renderer.connect("edited", self.new_value)
        combostore = Gtk.ListStore(content_type)
        for value in values:
            combostore.append([value])
        combo_renderer.set_property("model", combostore)
        self.add_column(column_name,
                        column_tooltip,
                        combo_renderer,
                        content_type)
        
    def new_value(self, cellrenderer, path, new_value):
        liststore = self.get_model()
        path, column = self.get_cursor()
        column_nr = column.colnr
        
        if self.column_types[column_nr] == GObject.TYPE_INT:
            try:
                new_value = int(new_value)
            except ValueError:
                locked_print("Falsche Eingabe, "
                             "Sie haben keinen Wert eingegeben, "
                             "der in den Typ Integer umgewandelt werden kann.")
            else:
                liststore[path][column_nr] = new_value
                self.save_changes(path, column_nr, new_value)
        
        elif self.column_types[column_nr] == GObject.TYPE_DOUBLE:
            try:
                # dot needed for float-conversion (instead of comma)
                new_value = float(new_value.replace(",", "."))
            except ValueError:
                locked_print("Falsche Eingabe: "
                             "Sie haben keinen Wert eingegeben, "
                             "der in den Typ Float umgewandelt werden kann.")
            else:
                liststore[path][column_nr] = new_value
                self.save_changes(path, column_nr, new_value)
        else:
            liststore[path][column_nr] = new_value
            self.save_changes(path, column_nr, new_value)
            
    def save_changes(self):
        raise RuntimeError("The method 'save_changes' must be implemented in "
                           "the child classes.")
        
class FunctionTreeView(TreeView):    
    def __init__(self):
        TreeView.__init__(self, "FunctionTreeView")
        self.add_text_colum("Bezeichnung",
                            "Name der Funktion ('Licht', 'Hupe' ...)",
                            GObject.TYPE_STRING)
        self.add_text_colum("Funktion",
                            "Die Nummer der Funktion im Lokdecoder",
                            GObject.TYPE_INT)
        self.add_combo_colum("Wert",
                             "Voreingestellter Zustand der Funktion: "
                             "An oder Aus",
                             GObject.TYPE_STRING,
                             ("An", "Aus"))
        self.add_text_colum("Gamepad-Button",
                            "Button am Gamepad zum Schalten der Funktion",
                            GObject.TYPE_INT)
        self.add_combo_colum("Schaltart",
                             "Taster oder Umschalter",
                             GObject.TYPE_STRING,
                             ("Umschalter", "Taster"))
        self.update_model()
        
        self.set_vexpand(True)
        self.set_hexpand(True)
    
    def load(self, functions):
        self.liststore.clear()
        for function in functions:
            if function.state:
                state = "An"
            else:
                state = "Aus"
            if function.toggle_mode == config.ToggleMode.PUSH:
                toggle_mode = "Taster"
            else:
                toggle_mode = "Umschalter"
            self.liststore.append([function.name,
                                   function.nr,
                                   state,
                                   function.button,
                                   toggle_mode])
        
    def save_changes(self, path, column_nr, new_value):
        if new_value == "An":
            new_value = True
        elif new_value == "Aus":
            new_value = False
        elif new_value == "Taster":
            new_value = config.ToggleMode.PUSH
        elif new_value == "Umschalter":
            new_value = config.ToggleMode.SWITCH
        setattr(Config.active_loco.functions[path.get_indices()[0]],
                Config.function_attributes[column_nr][0],
                new_value)
        
class LocoTreeView(TreeView):
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
        
        TreeView.__init__(self, "LocoTreeView")
        self.add_text_colum("Zu konfigurierende Lok wählen",
                            "Lok auswählen",
                            GObject.TYPE_STRING)
        self.update_model()

        self.connect("cursor-changed", self.loco_selected)
        self.set_vexpand(True)

    def loco_selected(self, treeview):
        path = self.get_cursor()[0]
        if path != None:
            row = path.get_indices()[0]
            Config.active_loco = Config.locos[row]
            self.function_treeview.load(Config.active_loco.functions)
            self.loco_properties_frame.load(Config.active_loco)
            self.decoder_frame.load(Config.active_loco)
            self.speed_frame.load(Config.active_loco)
        
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

class EventSoundTreeView(TreeView):
    def __init__(self, popup):
        self.popup = popup
        TreeView.__init__(self, "EventSoundTreeView")
        self.add_text_colum("Bezeichnung",
                            "Name des Geräusches "
                            "(Bremsenquietschen ...)",
                            GObject.TYPE_STRING)
        self.add_non_editable_text_colum("Geräuschdatei",
                                         "Datei für die Wiedergabe "
                                         "('*.wav' oder '*.ogg')",
                                         GObject.TYPE_STRING)
        self.add_combo_colum("Wert",
                             "Voreingestellter Zustand "
                             "der Funktion: "
                             "An oder Aus",
                             GObject.TYPE_STRING,
                             ("An", "Aus"))
        self.add_text_colum("v<sub>min</sub>",
                            "Mindestgeschwindigkeit",
                            GObject.TYPE_STRING)
        self.add_text_colum("v<sub>max</sub>",
                            "Maximalgeschwindigkeit",
                            GObject.TYPE_STRING)
        self.add_text_colum("a<sub>min</sub>",
                            "Mindestbeschleunigung "
                            "(kann negativ sein)",
                            GObject.TYPE_STRING)
        self.add_text_colum("a<sub>max</sub>",
                            "Maximalbeschleunigung "
                            "(kann negativ sein)",
                            GObject.TYPE_STRING)
        self.add_text_colum("Gamepad-Button",
                            "Button am Gamepad mit dem "
                            "das Geräusch aktiviert "
                            "werden kann",
                            GObject.TYPE_INT)
        self.update_model()
        
        self.connect("row-activated", self.choose_sound)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
    def choose_sound(self, treeview, path, column):
        column_nr = column.colnr
        if column_nr == 1:
            file_chooser_dialog = dialog_templates.SoundLoadDialog(self.popup)
            response = file_chooser_dialog.run()
            if response == Gtk.ResponseType.OK:
                file_path = file_chooser_dialog.get_filename()
                self.liststore.set_value(self.liststore.get_iter(path),
                                         column_nr,
                                         file_path)
                self.save_changes(path, column_nr, file_path)
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
                # take standard value
                new_value = Config.event_sound_attributes[column_nr][1]
                self.get_model()[path][column_nr] = "Egal"
        setattr(Config.active_loco.engine.event_sounds[path.get_indices()[0]],
                Config.event_sound_attributes[column_nr][0],
                new_value)
        
class FunctionSoundTreeView(TreeView):
    def __init__(self, popup):
        self.popup = popup
        TreeView.__init__(self, "FunctionSoundTreeView")
        
        self.add_text_colum("Bezeichnung",
                            "Name des Geräusches "
                            "(Hupe ...)",
                            GObject.TYPE_STRING)
        self.add_non_editable_text_colum("Geräuschdatei",
                                         "Datei für die Wiedergabe "
                                         "('*.wav' oder '*.ogg')",
                                         GObject.TYPE_STRING)
        self.add_combo_colum("Wert",
                             "Voreingestellter Zustand "
                             "der Funktion: "
                             "An oder Aus",
                             GObject.TYPE_STRING,
                             ("An", "Aus"))
        self.add_text_colum("Gamepad-Button",
                            "Button am Gamepad mit dem "
                            "das Geräusch aktiviert "
                            "werden kann",
                            GObject.TYPE_INT)
        self.add_combo_colum("Schaltart",
                             "Art und Weise auf die die "
                             "Funktion durch einen "
                             "Gamepad-Button geschaltet wird: "
                             "Taster, Umschalter oder Anschalter",
                             GObject.TYPE_STRING,
                             ("Umschalter",
                              "Taster (Einmal abspielen)",
                              "Taster (Mehrmals abspielen)",
                              "Anschalter (bis Geräuschende)"))
        self.update_model()
        
        self.connect("row-activated", self.choose_sound)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
    def choose_sound(self, treeview, path, column):
        column_nr = column.colnr
        if column_nr == 1:
            file_chooser_dialog = dialog_templates.SoundLoadDialog(self.popup)
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
                if func_sound.toggle_mode == config.ToggleMode.PUSH:
                    toggle_mode = "Taster (Mehrmals abspielen)"
                elif func_sound.toggle_mode == config.ToggleMode.PUSH_LIMITED:
                    toggle_mode = "Taster (Einmal abspielen)"
                elif func_sound.toggle_mode == config.ToggleMode.SWITCH:
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
            new_value = config.ToggleMode.PUSH
        elif new_value == "Taster (Einmal abspielen)":
            new_value = config.ToggleMode.PUSH_LIMITED
        elif new_value == "Umschalter":
            new_value = config.ToggleMode.SWITCH
        elif new_value == "Anschalter (bis Geräuschende)":
            new_value = config.ToggleMode.TAP
        setattr(Config.active_loco.function_sounds[path.get_indices()[0]],
                Config.function_sound_attributes[column_nr][0],
                new_value)

class ControlPointGraph(Gtk.DrawingArea):
    # minimum width + height
    width = 550
    height = 340
    # important: border_left_bottom must be larger than
    # radius_large + the width/height of the axes!
    border_left_bottom = 60.0
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
        # we dont use the special popup class since we dont
        # need the replace-content-functionality
        self.popup = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
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
                    cr.arc(x_abs,
                           y_abs,
                           self.radius_small,
                           0,
                           2 * pi)
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
                cr.arc(x_abs_1,
                       y_abs_1,
                       self.radius_large - self.control_point_border_width,
                       0,
                       2 * pi)
                cr.fill()
            
            cr.set_source_rgb(*self.control_point_outer_color)
            cr.arc(x_abs_2, y_abs_2, self.radius_large, 0, 2 * pi)
            cr.fill()
            cr.set_source_rgb(*self.control_point_inner_color)
            cr.arc(x_abs_2,
                   y_abs_2,
                   self.radius_large - self.control_point_border_width,
                   0,
                   2 * pi)
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
            if circle_left_end < x < circle_right_end \
            and circle_upper_end < y < circle_lower_end:
                result = nr, point
                break
        return result
    
    def get_abs_coords(self, x, y):
        return self.border_left_bottom + x * self.x_factor, \
               self.height - self.border_left_bottom - y * self.y_factor
    
    def get_speed_coords(self, x, y):
        return (x - self.border_left_bottom) / self.x_factor, \
               (self.height - self.border_left_bottom - y) / self.y_factor
    
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
                self.popup.label.set_text(str("%0.2f" % point[0]) +
                                          "\n" + str("%0.2f" % point[1]))
                self.popup.show_all()
        else:
            x, y = self.get_speed_coords(event.x, event.y)
            self.func.add_control_point(x, y)
            self.queue_draw()
            self.update_config_object()
            
    def update_config_object(self):
        Config.unsaved_changes(self.func,
                               "control_points",
                               self.func.control_points)
        Config.unsaved_changes(self.func,
                               "func_segments",
                               self.func.func_segments)
    
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
            self.popup.label.set_text(str("%0.2f" % new_point[0]) + "\n" +
                                      str("%0.2f" % new_point[1]))
                
    def create_coordinate_system(self):
        self.coordinate_system = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                                    self.width,
                                                    self.height)
        c = cairo.Context(self.coordinate_system)
        c.set_line_width(2)
        c.select_font_face("sans-serif")
        c.set_font_size(14)
        c.set_source_rgb(*self.legend_color)
        
        x_res = self.get_resolution(20.0, self.x_max, self.x_res_list) 
        y_res = self.get_resolution(20.0, self.y_max, self.y_res_list)
        
        decimal_places_y_res = y_res - int(y_res)
        decimal_places_y_max = self.y_max - int(self.y_max)
        # calculate number with most digits
        max_digits = float(max(decimal_places_y_res,
                               decimal_places_y_max,
                               key=lambda dec: len(str(dec))))
        if max_digits != 0:
            max_digits_number = int(self.y_max) + max_digits
        else:
            max_digits_number = int(self.y_max)
        
        # calculate highest possible width of a number-label at y-axis
        max_width, height = c.text_extents(str(max_digits_number))[2:4]
        
        x_axis_y_start = self.height - self.border_left_bottom + \
                         self.radius_large + self.axis_distance
        x_axis_y_end = self.height - self.border_left_bottom + \
                       self.radius_large + self.axis_distance + \
                       self.coordinate_line_length + height
        
        y_axis_x_start = self.border_left_bottom - self.radius_large - \
                         self.axis_distance - self.coordinate_line_length - \
                         max_width
        y_axis_x_end = self.border_left_bottom - self.radius_large - \
                       self.axis_distance
        
        x_legend_width, x_legend_height = c.text_extents(self.x_legend_text)[2:4]
        y_legend_width, y_legend_height = c.text_extents(self.y_legend_text)[2:4]
        
        c.move_to(0.5 * (self.width - self.border_left_bottom - x_legend_width),
                  x_axis_y_end + 0.5 * (self.height - x_axis_y_end + x_legend_height))
        c.show_text(self.x_legend_text)

        c.move_to(0.5 * (y_axis_x_start + y_legend_height),
                  0.5 * (self.height - self.border_left_bottom + y_legend_width))
        c.rotate(pi / -2.0)
        c.show_text(self.y_legend_text)
        c.rotate(pi / 2.0)
        c.set_font_size(12)
        c.set_source_rgb(*self.axes_color)
        
        pos = 0
        used_width = 0
#        abs_x_max = self.get_abs_coords(self.x_max, 0)[0]
        while pos <= self.x_max + x_res:
            text, x, y, width, height = self.get_axis_data_at_pos(c,
                                                                  pos,
                                                                  x_res,
                                                                  self.x_max)
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
            text, x, y, width, height = self.get_axis_data_at_pos(c,
                                                                  pos,
                                                                  y_res,
                                                                  self.y_max)
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
            # FIXME: if float returned by Gtk.SpinButton is converted to int,
            # the int has the wrong value (test with 104.0)
            value = int(max_value)
        else:
            value = int(pos)
        text = str(value)
        x, y = self.get_abs_coords(value, value)
        width, height = c.text_extents(text)[2:4]
        return text, x, y, width, height
    
    def calc_size_factors(self):
        self.x_factor = (self.width - self.border_left_bottom -
                         self.radius_large - self.border_right) / float(self.x_max)
        self.y_factor = (self.height - self.border_left_bottom -
                         self.radius_large) / float(self.y_max)
        
    def get_needed_space(self):
        return self.border_left_bottom, \
               self.border_right + self.radius_large
    
    def clear(self):
        # all attribs must be set at once in get_func_data,
        # so we only need to check if one of them exists
        if hasattr(self, "func"):
            del self.func
            del self.x_max
            del self.y_max
        self.queue_draw()
        
    def load(self, config_object):
        # every child-class must implement this method to set up axes
        self.get_func_data(config_object)
        self.calc_size_factors()
        self.create_coordinate_system()
        self.queue_draw()

class SpeedStepGraph(ControlPointGraph):
    x_legend_text = "Geschwindigkeit in km/h"
    y_legend_text = "Fahrstufe"
    
    # list of acceptable x-resolutions
    x_res_list = (0.05, 0.1, 0.2, 0.25, 0.5,
                  1, 2.5, 5, 10, 20, 50)
    y_res_list = (1, 2, 10)
    
    def __init__(self):
        ControlPointGraph.__init__(self, 128)
    
    def get_func_data(self, loco):
        self.x_max = loco.max_speed
        self.y_max = loco.speed_steps
        self.func = loco.speed_to_step_func

class EngineDialog(WarningDialog):
    sound_labels = {config.EngineType.DIESEL: "Verbrennungsmotor",
                    config.EngineType.STEAM: "Dampf",
                    None: "Kein Geräusch"}
    def __init__(self, engine_type, main_window):
        WarningDialog.__init__(self,
                               main_window,
                               "Durch Änderung des Geräuschmodells zu \"" +
                               self.sound_labels[engine_type] +
                               "\" werden die momentan festgelegten "
                               "Geräuschdateien zurückgesetzt!",
                               ["Abbrechen", 0, "Geräuschmodell ändern", 1])
        
class SpeedSoundFrame(Gtk.Frame):
    loco_sound_bars = {}
    engine_types = ((None, "Kein Geräusch"),
                    ("steam", "Dampf"),
                    ("diesel", "Verbrennungsmotor"))
    loading = False
    inner_margin = 10
    
    def __init__(self, graph, main_window):
        Gtk.Frame.__init__(self)
        self.speed_graph = graph
        self.main_window = main_window
        self.grid = Gtk.Grid()
        
        liststore = Gtk.ListStore(GObject.TYPE_STRING)
        for unused_engine_type, type_def in self.engine_types:
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
        
        self.popup = Popup(main_window,
                           "Geräusch-Ereignisse",
                           Gdk.WindowTypeHint.NORMAL)
        self.event_sound_frame = EventSoundFrame(self.popup)
        self.popup.set_content(self.event_sound_frame)
        
        self.set_horizontal_margins()
        self.add(self.grid)        
    
    # the loco has changed -> update the type_combo + sound_options
    def load(self, loco):
        # prevent type_combos callback from being called
        # when a new loco is loaded
        self.loading = True
        self.loco = loco
        self.remove_sound_options()
        if loco.engine != None:
            self.type_combo.set_value(loco.engine.type)
            self.create_sound_options()
#            self.event_sound_frame.treeview.load(loco.engine.event_sounds)
        else:
            self.type_combo.set_value(None)
        self.loading = False
        
    def create_sound_options(self):
        self.table = EntryTable(True,
                                False,
                                Gtk.Orientation.HORIZONTAL,
                                3)
        if self.loco.engine.type == config.EngineType.DIESEL:
            self.table.add_sound_file_entry("Start-Geräusch",
                                            "Geräusch für das Starten der Lokomotive",
                                            "start_sound")
            self.table.add_sound_file_entry("Leerlaufgeräusch",
                                            "Geräusch im Leerlauf",
                                            "idle_sound")
            self.table.add_sound_file_entry("Abstellgeräusch",
                                            "Geräusch für das Herunterfahren "
                                            "/ Abstellen der Lokomotive",
                                            "quit_sound")
        else:
            self.table.add_sound_file_entry("Leerlaufgeräusch",
                                            "Geräusch im Leerlauf",
                                            "idle_sound")
            self.table.add_sound_file_entry("Dampfablass-Geräusch",
                                            "Geräusch beim Ausströmen von Dampf "
                                            "aus den Zylindern",
                                            "cylinder_steam_sound")
            self.table.add_int_entry("Takte",
                                     "Anzahl der Zylinder-Takte der Dampflok",
                                     "nr_strokes")
            self.table.add_float_entry("Dampfablass-Dauer",
                                       "Zeit in der Dampf aus den Zylindern strömt "
                                       "bevor der erste Zylinder-Schlag ertönt in s",
                                       "stroke_start_delay")
            self.table.add_float_entry("Treibrad-Durchmesser",
                                       "Durchmesser eines Antriebsrades in m",
                                       "wheel_diameter",
                                       0.1, 99, 0.001)
            self.table.add_float_entry("Minimale Taktfrequenz",
                                       "Die kleinstmögliche Frequenz in "
                                       "Takten pro s",
                                       "min_freq")
            
        self.table.add_action_button("Geräusch-Ereignisse",
                                     "Wiedergabe von Geräuschdateien anhand "
                                     "bestimmter Ereignisse festlegen",
                                     "Bearbeiten",
                                     self.edit_sounds)
        self.table.set_halign(Gtk.Align.END)
        self.table.load(self.loco.engine)            
        self.table.show_all()
        self.grid.attach(self.table, 1, 0, 1, 1)
        
        # test if engine displayed in sound-bar is still the same as in loco (if not, new sound-bar is needed)
        if self.loco in self.loco_sound_bars \
        and self.loco_sound_bars[self.loco].engine == self.loco.engine:
            self.sound_bar = self.loco_sound_bars[self.loco]
        else:
            self.sound_bar = SegmentedSoundBar(self.speed_graph,
                                               self, self.main_window)
            self.sound_bar.load(self.loco)
            self.sound_bar.set_horizontal_margins(self.inner_margin - 0.5 * 
                                                  self.sound_bar.handle_width)
            self.loco_sound_bars[self.loco] = self.sound_bar
        self.grid.attach_next_to(self.separator,
                                 self.type_combo,
                                 Gtk.PositionType.BOTTOM, 2, 1)
        self.grid.attach_next_to(self.sound_bar,
                                 self.separator,
                                 Gtk.PositionType.BOTTOM, 2, 1)
        self.event_sound_frame.treeview.load(self.loco.engine.event_sounds)
        
        
    def remove_sound_options(self):
        if self.separator.get_parent() != None:
            self.popup.hide()
            self.grid.remove(self.separator)
            self.grid.remove(self.sound_bar)
            self.grid.remove(self.table)
            del self.sound_bar
            
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
            if self.loco.engine != None:
                engine_dialog = EngineDialog(new_engine_type, self.main_window)
                response = engine_dialog.run()
                engine_dialog.destroy()
            else:
                response = True
            if response:
                self.remove_sound_options()
                if new_engine_type == None:
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
        
    def edit_sounds(self, button):
        self.popup.show_at_mouse()

class CustomHandlePaned(Gtk.Paned):
    def __init__(self):
        Gtk.Paned.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_name("custom-handle-paned")
        self.set_hexpand(True)
        # Attention: these values only fit to the shipped handle-icon!
        self.set_size_request(-1, 30)

class SegmentedSoundBar(Gtk.Grid):
    # has to fit the width set in gtk_styles_and_transitions.css
    handle_width = 6
    
    def __init__(self, graph, speed_sound_frame, main_window):
        Gtk.Grid.__init__(self)
        self.graph = graph
        self.speed_sound_frame = speed_sound_frame
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.left_handle = Gtk.Image.new_from_file(normpath("icons/sound-bar-pane-handle3.png"))
        self.left_handle.set_halign(Gtk.Align.START)
        self.right_handle = Gtk.Image.new_from_file(normpath("icons/sound-bar-pane-handle3.png"))
        self.right_handle.set_halign(Gtk.Align.END)
        self.add(self.left_handle)
        self.add(self.right_handle)
        self.set_margin_top(5)
        self.popup = Popup(main_window)
        
        
    def load(self, loco):
        # needed by SoundSelectorButton
        self.loco = loco
        # needed for comparison with the current loco.engine in SpeedSoundFrame
        # to find out if new soundbar is needed
        self.engine = loco.engine
        if hasattr(self, "paned"):
            self.remove(self.parent_paned)
            self.parent_paned.destroy()
        self.paned = CustomHandlePaned()
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
                                                  "Geräusch " + str(nr + 1),
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
                new_paned = CustomHandlePaned()
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
    if engine_type == config.EngineType.DIESEL:
        return DieselSoundSelectorButton(*args)
    elif engine_type == config.EngineType.STEAM:
        return SteamSoundSelectorButton(*args)

class SoundSelectorButton(PopupButton):    
    def __init__(self, text, popup, segment, sound_bar):
        PopupButton.__init__(self, text, True, popup)
        
        self.grid = Gtk.Grid()
        
        delete_sound_button = StockImageButton("Geräusch löschen",
                                               Gtk.STOCK_DELETE)
        delete_sound_button.set_halign(Gtk.Align.START)
        delete_sound_button.connect("clicked", self.delete_sound)
        self.grid.attach(delete_sound_button, 0, 1, 1, 1)
        
        insert_sound_button = StockImageButton("Geräusch rechts einfügen",
                                               Gtk.STOCK_ADD)
        insert_sound_button.set_halign(Gtk.Align.END)
        insert_sound_button.connect("clicked", self.insert_sound)
        self.grid.attach(insert_sound_button, 1, 1, 1, 1)
        
        self.close_button = StockImageButton("Schließen",
                                             Gtk.STOCK_CLOSE)
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
            if self.segment.position == config.SegmentPosition.UPPER:
                prev_segment.set_position(config.SegmentPosition.UPPER)
            self.sound_bar.load(loco)
            Config.unsaved_changes(loco.engine,
                                   "sound_segments",
                                   loco.engine.sound_segments)
        else:
            del self.sound_bar.speed_sound_frame.loco_sound_bars[loco]
            # type_combo will take care of setting loco.engine = None
            self.sound_bar.speed_sound_frame.type_combo.set_value(None)
        self.popup.hide()
        
    def insert_sound(self, button):
        sound_bar = self.sound_bar
        loco = self.sound_bar.loco
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
    def __init__(self, text, popup, segment, sound_bar):
        SoundSelectorButton.__init__(self, text, popup, segment, sound_bar)
        self.table = EntryTable(True, False)
        self.table.add_sound_file_entry("Unter Last:",
                                        "Geräusch das im gewählten "
                                        "Geschwindigkeitsbereich \nunter "
                                        "Last abgespielt wird",
                                        "load_sound")
        self.table.add_sound_file_entry("Im Leerlauf:",
                                        "Geräusch das im gewählten "
                                        "Geschwindigkeitsbereich\nim "
                                        "Leerlauf abgespielt wird",
                                        "idle_sound")
        if not segment.position == config.SegmentPosition.UPPER:
            self.table.add_sound_file_entry("Beschleunigungsvorgang:",
                                            "Beschleunigungsvorgang zu dieser "
                                            "Geräusch-Stufe",
                                            "accel_sound")
        self.table.add_sound_file_entry("Bremsvorgang:",
                                        "Bremsvorgang zur vorherigen "
                                        "Geräusch-Stufe",
                                        "decel_sound")
        self.set_content(self.table)
        
    # override standard implementation (include loading)
    def show_popup(self, button):
        self.table.load(self.segment)
        self.popup.set_content(self.grid)
        self.popup.show_at_mouse()
        
class SteamSoundSelectorButton(SoundSelectorButton):    
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
            self.segment.stroke_sounds = [None for unused_i in xrange(nr_strokes)]
        
    def show_popup(self, button):
        self.set_content(self.create_grid())
        self.popup.set_content(self.grid)
        self.popup.show_at_mouse()
        
    def file_set(self, button, stroke_nr):
        self.segment.stroke_sounds[stroke_nr] = button.retrieve_value()
        Config.unsaved_changes(self.segment,
                               "stroke_sounds",
                               self.segment.stroke_sounds)

class Popup(Gtk.Window):
    def __init__(self, main_window, title="",
                 type_hint=Gdk.WindowTypeHint.TOOLTIP):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        self.set_title("Electrip " + ELECTRIP_VERSION + " - " + title)
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
    
    # can be called multiple times
    def set_content(self, widget):
        if hasattr(self, "content"):
            self.remove(self.content)
        self.resize_to_geometry(1, 1)
        self.content = widget
        self.add(self.content)
        
    def delete_event(self, window, event):
        self.hide()
        return True
