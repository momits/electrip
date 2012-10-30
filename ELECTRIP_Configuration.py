#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository import GObject, Gtk, Pango, Gdk
import cairo
import config
from math import pi
from Constants import *
from ELECTRIP import StockImageButton
import SaveAndLoad
from LockedPrint import locked_print

class MainBox(Gtk.Notebook):
    def __init__(self, config, main_window):
        Gtk.Notebook.__init__(self)
        global Config
        Config = config
        self.loco_function_frame = LocoFunctionFrame()
        self.loco_speed_frame = LocoSpeedGraphFrame()
        self.loco_properties_frame = LocoPropertiesFrame(main_window, self.loco_speed_frame.graph)

        self.scrolled_window_loco_selection = ScrolledTreeView(LocoSelectionTreeView(self.loco_properties_frame, self.loco_function_frame, self.loco_speed_frame))
        self.buttonbox_loco = ButtonBoxLocoActions(self.scrolled_window_loco_selection.treeview, self.loco_properties_frame, self.loco_function_frame, self.loco_speed_frame)
        
        self.loco_grid = Gtk.Grid()
        self.loco_grid.attach(self.scrolled_window_loco_selection, 0, 0, 1, 1)
        self.loco_grid.attach(self.buttonbox_loco, 0, 1, 1, 1)
        self.loco_grid.attach(Gtk.Separator.new(Gtk.Orientation.VERTICAL), 1, 0, 1, 2)
        
        self.scrolled_window_loco_properties = Gtk.ScrolledWindow()
        self.loco_properties_grid = Gtk.Grid()
        self.loco_properties_grid.attach(self.loco_properties_frame, 0, 0, 1, 1)
        self.loco_properties_grid.attach(self.loco_function_frame, 1, 0, 1, 1)
        self.loco_properties_grid.attach(self.loco_speed_frame, 0, 1, 2, 1)
        self.scrolled_window_loco_properties.add_with_viewport(self.loco_properties_grid)
        
        self.loco_grid.attach(self.scrolled_window_loco_properties, 2, 0, 1, 1)
        self.append_page(self.loco_grid, Gtk.Label("Lokomotiven"))
        
        self.server_table = ServerTable()
        self.append_page(TopAlignment(self.server_table), Gtk.Label("SRCP-Server"))
        
        self.joystick_table = JoystickTable()
        self.append_page(TopAlignment(self.joystick_table), Gtk.Label("Gamepad"))
        self.show_all()

class NewLocoButton(Gtk.Button):
    def __init__(self, loco_selection_treeview, loco_property_frame, loco_function_frame):
        Gtk.Button.__init__(self, "Neue Lok")
        self.connect("clicked", self.new_loco, loco_selection_treeview, loco_property_frame, loco_function_frame)
        
    def new_loco(self, button, loco_selection_treeview, loco_property_frame, loco_function_frame):
        loco_selection_treeview.new_loco()
        Config.unsaved_changes(Config, "locos", Config.locos)

class DeleteLocoButton(Gtk.Button):
    def __init__(self, loco_selection_treeview, loco_property_frame, loco_function_frame, loco_speed_frame):
        Gtk.Button.__init__(self, "Lok löschen")
        self.connect("clicked", self.delete_loco, loco_selection_treeview, loco_property_frame, loco_function_frame, loco_speed_frame)
        
    def delete_loco(self, button, loco_selection_treeview, loco_property_frame, loco_function_frame, loco_speed_frame):
        path = loco_selection_treeview.get_cursor()[0]
        try:
            row = loco_selection_treeview.liststore.get_iter(path)
        except TypeError:
            locked_print("Keine Zeile ausgewählt.")
        else:
            liststore = loco_function_frame.scrolled_window.treeview.get_model()
            loco_function_frame.scrolled_window.treeview.function_liststores.remove(liststore) # Aktuelle Funktionsliste löschen
            loco_selection_treeview.liststore.remove(row) # Zeile im Liststore löschen
            Config.locos.pop(path.get_indices()[0])
            Config.unsaved_changes(Config, "locos", Config.locos)
                
            if len(loco_selection_treeview.liststore) == 0:
                loco_speed_frame.graph.clear()
                loco_property_frame.set_sensitive(False)
                loco_function_frame.set_sensitive(False)
                loco_speed_frame.set_sensitive(False)
            
        

class NewLocoFunctionButton(Gtk.Button):
    def __init__(self, loco_function_treeview):
        Gtk.Button.__init__(self, "Neue Funktion")
        self.connect("clicked", self.new_function, loco_function_treeview)
        
    def new_function(self, button, loco_function_treeview):
        liststore = loco_function_treeview.get_model()
        try:
            loco_id = loco_function_treeview.function_liststores.index(liststore)
        except TypeError:
            locked_print("Keine Lok ausgewählt.")
        else:
            function = config.Function(Config.unsaved_changes)
            loco = Config.locos[loco_id]
            loco.functions.append(function)
            Config.unsaved_changes(Config.locos[loco_id], "functions", Config.locos[loco_id].functions)  # call unsaved changes method manually, cause list object "functions" doesnt do this
            loco_function_treeview.function_liststores[loco_id].append([function.name, function.nr, "An", function.button, "Umschalter"])
            
class DeleteLocoFunctionButton(Gtk.Button):
    def __init__(self, loco_function_treeview):
        Gtk.Button.__init__(self, "Funktion löschen")
        self.connect("clicked", self.delete_function, loco_function_treeview)
        
    def delete_function(self, button, loco_function_treeview):
        liststore = loco_function_treeview.get_model() # Aktuelle Funktionsliste finden
        path = loco_function_treeview.get_cursor()[0]
        if path != None:
            row = liststore.get_iter(path) # Zu löschende Zeile im Liststore finden
            liststore.remove(row) # Zeile im Liststore löschen
            loco_id = loco_function_treeview.function_liststores.index(liststore)
            Config.locos[loco_id].functions.pop(path.get_indices()[0])
            Config.unsaved_changes(Config.locos[loco_id], "functions", Config.locos[loco_id].functions) # call unsaved changes method manually, cause list object "functions" doesnt do this
        else:
            locked_print("Keine Funktion ausgewählt.")
            
class ArrowButton(Gtk.Button):
    def __init__(self, direction): # direction: True = nach oben
        Gtk.Button.__init__(self)
        self.direction = direction
        if direction:
            self.set_image(Gtk.Arrow.new(Gtk.ArrowType.UP, Gtk.ShadowType.NONE))
        else:
            self.set_image(Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.NONE))

class ButtonBoxLocoActions(Gtk.ButtonBox):
    def __init__(self, loco_selection_treeview, loco_property_frame, loco_function_frame, loco_speed_frame):
        Gtk.ButtonBox.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_layout(Gtk.ButtonBoxStyle.START)
        self.set_vexpand(False)
        self.add_loco_button = NewLocoButton(loco_selection_treeview, loco_property_frame, loco_function_frame)
        self.delete_loco_button = DeleteLocoButton(loco_selection_treeview, loco_property_frame, loco_function_frame, loco_speed_frame)
        self.move_up_button = ArrowButton(True)
        self.move_up_button.connect("clicked", self.clicked, loco_selection_treeview, loco_function_frame.scrolled_window.treeview)
        self.move_down_button = ArrowButton(False)
        self.move_down_button.connect("clicked", self.clicked, loco_selection_treeview, loco_function_frame.scrolled_window.treeview)
        
        self.add(self.add_loco_button)
        self.add(self.delete_loco_button)
        self.add(self.move_up_button)
        self.add(self.move_down_button)

    def clicked(self, button, loco_selection_treeview, loco_function_treeview):
        path, column = loco_selection_treeview.get_cursor()
        try:
            row = loco_selection_treeview.liststore.get_iter(path)
        except TypeError:
            locked_print("Es ist keine Lok ausgewählt, es kann nichts verschoben werden.")
        else:
            row_nr = path.get_indices()[0]
            if button.direction and row_nr > 0: # wenn verschiebe-richtung nach oben und row nicht ganz oben steht
                prev_row = loco_selection_treeview.liststore.iter_nth_child(None, row_nr - 1)
                loco_function_treeview.function_liststores.insert(row_nr - 1, loco_function_treeview.function_liststores.pop(row_nr)) # Funktionen-Liststore an andere Stelle setzen
                loco_selection_treeview.liststore.move_before(row, prev_row)
                Config.locos.insert(row_nr - 1, Config.locos.pop(row_nr))
                Config.unsaved_changes(Config, "locos", Config.locos)
                loco_selection_treeview.set_cursor(Gtk.TreePath.new_from_string(str(row_nr - 1)), None, False)
            elif not button.direction and row_nr < len(loco_selection_treeview.liststore) - 1:
                following_row = loco_selection_treeview.liststore.iter_nth_child(None, row_nr + 1)
                loco_function_treeview.function_liststores.insert(row_nr + 1, loco_function_treeview.function_liststores.pop(row_nr)) # Funktionen-Liststore an andere Stelle setzen
                loco_selection_treeview.liststore.move_after(row, following_row)
                Config.locos.insert(row_nr + 1, Config.locos.pop(row_nr))
                Config.unsaved_changes(Config, "locos", Config.locos)
                loco_selection_treeview.set_cursor(Gtk.TreePath.new_from_string(str(row_nr + 1)), None, False)
            else:
                locked_print("Lok befindet sich schon am Rand, kann nicht weiter verschoben werden.")

class ButtonBoxLocoFunctionActions(Gtk.ButtonBox):
    def __init__(self, loco_function_treeview):
        Gtk.ButtonBox.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_layout(Gtk.ButtonBoxStyle.START)
        self.add_function_button = NewLocoFunctionButton(loco_function_treeview)
        self.delete_function_button = DeleteLocoFunctionButton(loco_function_treeview)
        self.move_up_button = ArrowButton(True)
        self.move_up_button.connect("clicked", self.clicked, loco_function_treeview)
        self.move_down_button = ArrowButton(False)
        self.move_down_button.connect("clicked", self.clicked, loco_function_treeview)
        
        self.add(self.add_function_button)
        self.add(self.delete_function_button)
        self.add(self.move_up_button)
        self.add(self.move_down_button)
    
    def clicked(self, button, loco_function_treeview):
        liststore = loco_function_treeview.get_model()
        path, column = loco_function_treeview.get_cursor()
        try: 
            row = liststore.get_iter(path)
        except TypeError:
            locked_print("Es ist keine Funktion ausgewählt, es kann nichts verschoben werden.")
        else:
            row_nr = path.get_indices()[0]
            loco_id = loco_function_treeview.function_liststores.index(liststore)
            if button.direction and row_nr > 0: # wenn verschiebe-richtung nach oben und row nicht ganz oben steht
                prev_row = liststore.iter_nth_child(None, row_nr - 1)
                liststore.move_before(row, prev_row)
                Config.locos[loco_id].functions.insert(row_nr - 1, Config.locos[loco_id].functions.pop(row_nr))
                Config.unsaved_changes(Config.locos[loco_id], "functions", Config.locos[loco_id].functions)
                loco_function_treeview.set_cursor(Gtk.TreePath.new_from_string(str(row_nr - 1)), None, False)
            elif not button.direction and row_nr < len(liststore) - 1:
                following_row = liststore.iter_nth_child(None, row_nr + 1)
                liststore.move_after(row, following_row)
                Config.locos[loco_id].functions.insert(row_nr + 2, Config.locos[loco_id].functions.pop(row_nr))
                Config.unsaved_changes(Config.locos[loco_id], "functions", Config.locos[loco_id].functions)
                loco_function_treeview.set_cursor(Gtk.TreePath.new_from_string(str(row_nr + 1)), None, False)
            else:
                locked_print("Funktion befindet sich schon am Rand, kann nicht weiter verschoben werden.")
        #except AttributeError:
            #locked_print("Keine Lok (und damit keine Funktion) ausgewählt, es kann nichts verschoben werden.")

class BoldLabel(Gtk.Label):
    def __init__(self, text):
        super(BoldLabel, self).__init__()
        self.set_markup("<b>" + text + "</b>")

class TopAlignment(Gtk.Alignment):
    def __init__(self, child):
        super(TopAlignment, self).__init__()
        self.set(0.0, 0.0, 0.0, 0.0)
        self.add(child)

class LocoFunctionFrame(Gtk.Frame):
    def __init__(self):
        Gtk.Frame.__init__(self)
        self.set_border_width(10) # Schönheitsabstand
        self.set_label_widget(BoldLabel("Funktionen"))
                
        self.scrolled_window = ScrolledTreeView(LocoFunctionTreeView())
        self.buttonbox_function_actions = ButtonBoxLocoFunctionActions(self.scrolled_window.treeview)
        
        grid = Gtk.Grid()
        grid.attach(self.scrolled_window, 0, 0, 1, 1)
        grid.attach(self.buttonbox_function_actions, 0, 1, 1, 1)
        self.add(grid)
        self.set_sensitive(False)
        
class LocoSpeedGraphFrame(Gtk.Frame):
    notice_combo_change = False
    def __init__(self):
        Gtk.Frame.__init__(self)
        self.set_border_width(10) # Schönheitsabstand
        self.set_valign(Gtk.Align.START)
        self.set_label_widget(BoldLabel("Geschwindigkeitsverlauf"))
        
        self.graph = SpeedStepGraph()
        liststore = Gtk.ListStore(GObject.TYPE_INT)
        for value in [14, 27, 28, 128]:
            liststore.append([value])
        self.speed_steps_combo = EasyComboBox(liststore)
        self.speed_steps_combo.connect("changed", self.changed)
        self.speed_steps_combo.set_tooltip_text("Die Anzahl Fahrstufen des Lokdecoders")
        self.max_speed_spin_button = Gtk.SpinButton.new_with_range(1, 999, 0.1) # lowest possible speed is 1 km/h, highest possible 999
        self.max_speed_spin_button.connect("value-changed", self.changed)
        self.max_speed_spin_button.set_tooltip_text("Die reale Höchstgeschwindigkeit der Lokomotive in km/h")
        self.cancel_button = Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL)
        self.cancel_button.connect("clicked", self.set_graph, False)
        self.accept_button = Gtk.Button.new_from_stock(Gtk.STOCK_OK)
        self.accept_button.connect("clicked", self.set_graph, True)
        self.warn_image = Gtk.Image.new_from_stock(Gtk.STOCK_DIALOG_WARNING, Gtk.IconSize.BUTTON)
        self.warn_label = Gtk.Label("Durch Änderung der Achsen wird die Geschwindigkeitskennlinie zurückgesetzt")
        self.warn_label.set_vexpand(True)
        
        self.warn_grid = Gtk.Grid()
        self.warn_grid.set_column_spacing(5)
        self.warn_grid.set_halign(Gtk.Align.CENTER)
        self.warn_grid.set_valign(Gtk.Align.CENTER)
        self.warn_grid.attach(self.warn_image, 0, 0, 1, 1)
        self.warn_grid.attach(self.warn_label, 1, 0, 2, 1)
        self.warn_grid.attach(self.cancel_button, 1, 1, 1, 1)
        self.warn_grid.attach(self.accept_button, 2, 1, 1, 1)
        
        self.grid = Gtk.Grid()
        self.grid.set_row_spacing(5)
        self.grid.attach(self.graph, 0, 0, 3, 1)
        self.grid.attach(Gtk.Label("Anzahl Fahrstufen"), 0, 1, 1, 1)
        self.grid.attach(self.speed_steps_combo, 1, 1, 1, 1)
        self.grid.attach(Gtk.Label("Höchstgeschwindigkeit"), 0, 2, 1, 1)
        self.grid.attach(self.max_speed_spin_button, 1, 2, 1, 1)
        self.grid.attach(self.warn_grid, 2, 1, 1, 2)
        
        self.add(self.grid)
        self.set_sensitive(False)
        
    def changed(self, widget):
        if self.notice_combo_change:
            self.warn_grid.set_sensitive(True)
        

    def set_graph(self, widget, accept_changes):
        if accept_changes:
            self.loco.max_speed = self.max_speed_spin_button.get_value()
            self.loco.speed_steps = self.speed_steps_combo.retrieve_value()
            func = self.loco.speed_to_step_func
            func.control_points = [(0, 0), (float(self.loco.max_speed), float(self.loco.speed_steps))]
            func.func_segments = [func.calc_func_segment(*func.control_points[-2:])] # update the linear function between the two control points
            self.graph.load(self.loco)
        else:
            self.max_speed_spin_button.set_value(self.loco.max_speed)
            self.speed_steps_combo.set_value(self.loco.speed_steps)
        self.warn_grid.set_sensitive(False)
        
    def load(self, loco):
        self.loco = loco
        self.graph.load(loco)
        self.max_speed_spin_button.set_value(self.loco.max_speed)
        self.speed_steps_combo.set_value(self.loco.speed_steps)
        self.warn_grid.set_sensitive(False)

class ScrolledTreeView(Gtk.ScrolledWindow):
    def __init__(self, treeview):
        super(ScrolledTreeView, self).__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.treeview = treeview
        min_req, natural_req = self.treeview.get_preferred_size()
        self.set_size_request(natural_req.width, natural_req.height + 40)
        self.add(self.treeview)
        
class EntryTable(Gtk.Grid):
    def __init__(self, params_w_defs, config_object_attributes, use_tooltips, use_bold_params):
        Gtk.Grid.__init__(self)
        self.params_w_defs = params_w_defs
        self.config_object_attributes = config_object_attributes
        
        self.set_column_spacing(10)
        self.set_row_spacing(5)
        self.set_border_width(6) # Schönheitsabstand
        self.entry_fields = []
        y = 0
        for parameter, definition, input_type in self.params_w_defs:
            if input_type[0] == ENTRY_TABLE_INPUT_STRING:
                entry_field = Gtk.Entry()
                entry_field.retrieve_value = entry_field.get_text
                entry_field.set_value = entry_field.set_text
                entry_field.connect("changed", self.save_changes, config_object_attributes[y])
            elif input_type[0] == ENTRY_TABLE_INPUT_INT:
                entry_field = Gtk.SpinButton.new_with_range(0, 9999, 1)
                entry_field.retrieve_value = entry_field.get_value_as_int
                entry_field.connect("value-changed", self.save_changes, config_object_attributes[y])
            elif input_type[0] == ENTRY_TABLE_INPUT_FLOAT:
                entry_field = Gtk.SpinButton.new_with_range(0, 9999, 0.1)
                entry_field.retrieve_value = entry_field.get_value
                entry_field.connect("value-changed", self.save_changes, config_object_attributes[y])
            elif input_type[0] == ENTRY_TABLE_INPUT_COMBO:
                liststore = Gtk.ListStore(input_type[1])
                for value in input_type[2:len(input_type)]:
                    liststore.append([value])
                entry_field = EasyComboBox(liststore)
                entry_field.connect("changed", self.save_changes, config_object_attributes[y])
            elif input_type[0] == ENTRY_TABLE_INPUT_FILE:
                entry_field = EasyFileButton(input_type[1])
                entry_field.connect("selection-finished", self.save_changes, config_object_attributes[y])
            elif input_type[0] == ENTRY_TABLE_INPUT_BOOL:
                entry_field = Gtk.CheckButton.new()
                entry_field.retrieve_value = entry_field.get_active
                entry_field.set_value = entry_field.set_active
                entry_field.connect("toggled", self.save_changes, config_object_attributes[y])
            if use_bold_params:
                parameter_label = BoldLabel(parameter)
            else:
                parameter_label = Gtk.Label(parameter)
            self.attach(parameter_label, 0, y, 1, 1)
                
            if use_tooltips:
                entry_field.set_tooltip_text(definition)
            else:
                definition_label = Gtk.Label(label=definition)
                definition_label.set_alignment(0, 0.5)
                self.attach(definition_label, 2, y, 1, 1)
            
            self.attach(entry_field, 1, y, 1, 1)
            self.entry_fields.append(entry_field)
            y += 1
        
    def load(self, config_object):
        self.config_object = config_object
        for nr, config_attrib in enumerate(self.config_object_attributes):
            try:
                value = getattr(config_object, config_attrib)
            except AttributeError:
                locked_print("Attribut", config_attrib, "konnte nicht gefunden werden, es handelt sich evtl. um eine veraltete ELECTRIP-Datei.")
            else:
                if config_attrib == "direction":
                    if value: # we need to do the conversion between displayed value and saved value whenever they are of a different kind
                        value = "Vorwärts"
                    else:
                        value = "Rückwärts"
                self.entry_fields[nr].set_value(value)
            
    def save_changes(self, widget, config_attrib):
        value = widget.retrieve_value()
        if value == "Rückwärts": # we need to do the conversion between displayed value and saved value whenever they are of a different kind
            value = False
        elif value == "Vorwärts":
            value = True
        if getattr(self.config_object, config_attrib) != value: # only set attributes when they differ from what is already saved -> prevent signal-handler trouble on loading
            setattr(self.config_object, config_attrib, value)

class EasyComboBox(Gtk.ComboBox): # subclassed combobox with methods allowing to easily acces the displayed value
    def __init__(self, liststore):
        Gtk.ComboBox.__init__(self)
        self.set_model(liststore)
        renderer = Gtk.CellRendererText()
        self.pack_start(renderer, True)
        self.add_attribute(renderer, "text", 0)
        self.set_active(0)

    def retrieve_value(self):
        return self.get_model()[self.get_active()][0]
        
    def set_value(self, string):
        for row_nr, row in enumerate(self.get_model()):
            if string in row:
                self.set_active(row_nr)
                break
            
class EasyFileButton(Gtk.Grid):
    __gsignals__ = {
      "selection-finished": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }
    
    def __init__(self, main_window):
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.select_button = Gtk.Button("Datei wählen")
        self.select_button.connect("clicked", self.image_selection, main_window)
        self.label = self.select_button.get_child()
        self.label.set_ellipsize(Pango.EllipsizeMode.END)
        
        self.clear_button = StockImageButton(None, Gtk.STOCK_CLEAR)
        self.clear_button.connect("clicked", self.clear)
        self.add(self.select_button)
        self.add(self.clear_button)
        
    def retrieve_value(self):
        return self.label.get_text()
    
    def set_value(self, string):
        self.label.set_text(string)
        layout = self.label.get_layout()
        if layout.is_ellipsized(): # find out if the path can be displayed on the select_button without getting ellipsized
            self.set_tooltip_text(string)
        else:
            self.set_tooltip_text("Der Pfad an dem das passende Lokbild abgelegt ist")
        
    def image_selection(self, button, main_window):
        file_chooser_dialog = SaveAndLoad.ImageLoadDialog(main_window)
        response = file_chooser_dialog.run()
        if response == Gtk.ResponseType.OK:
            path = file_chooser_dialog.get_filename()
            self.set_value(path)
            self.emit("selection-finished")
        elif response == Gtk.ResponseType.CANCEL:
            locked_print('Laden abgebrochen.')
        file_chooser_dialog.destroy()
        
    def clear(self, button):
        self.set_value("Datei wählen")
        self.emit("selection-finished")

class LocoPropertiesFrame(Gtk.Frame):
    loco_attributes = ["address", "protocol", "accel_duration", "direction", "img_path"]
    def __init__(self, main_window, loco_speed_graph):
        Gtk.Frame.__init__(self)
        self.params_w_defs = [
("Adresse", "Die Adresse des Digitaldecoders der Lok", [ENTRY_TABLE_INPUT_INT]),
("Protokoll", """Das Digitalprotokoll, das vom Lokdecoder verwendet wird:
    -> M 1: MM, 80 Adressen, 14 Fahrstufen
    -> M 2: MM, 80 Adr., 14 Fahrst. (neuere Decoder)
    -> M 3: MM, Spezialprotokoll für sog. Wikingerdekoder
    -> M 4: MM, 256 Adressen, 14 Fahrst.
    -> M 5: MM, 256 Adressen, 28 Fahrst.
    -> N1: DCC kurzes Adressformat
    -> N2: DCC langes Adressformat""",
[ENTRY_TABLE_INPUT_COMBO, GObject.TYPE_STRING, "M 1", "M 2", "M 3", "M 4", "M 5", "N 1", "N 2"]),
("Beschleunigungsdauer", "Die Zeit in s, die benötigt wird, um die Geschwindigkeit der Lok bei voller Auslenkung des Joysticks von 0 auf den höchstmöglichen Wert zu bringen", [ENTRY_TABLE_INPUT_FLOAT]),
("Fahrtrichtung", "Die voreingestellte Fahrtrichtung der Lokomotive", [ENTRY_TABLE_INPUT_COMBO, GObject.TYPE_STRING, "Vorwärts", "Rückwärts"]),
("Bild", "Der Pfad an dem das passende Lokbild abgelegt ist", [ENTRY_TABLE_INPUT_FILE, main_window]) # this list is built in the __init__-method because 'main_window' is needed for the file-selection-dialog
]
        self.set_border_width(10) # Schönheitsabstand
        self.set_label_widget(BoldLabel("Allgemeine Eigenschaften"))
        
        self.table = EntryTable(self.params_w_defs, self.loco_attributes, True, False)
        self.add(self.table)
        self.set_sensitive(False)
        
class ServerTable(EntryTable): # every class using EntryTable defines two list: params_w_defs and some_attributes
    server_attributes = ["host", "port", "loco_bus", "power"]
    params_w_defs = [ # the list of attributes says which attribute of index a in the config_object maps to the Entry in EntryTable with index a
("Host", "Die IP-Adresse des Rechners auf dem der Server läuft", [ENTRY_TABLE_INPUT_STRING]),
("Port", "Der Port unter dem der Server erreichbar ist", [ENTRY_TABLE_INPUT_INT]),
("Bus", "Der Bus auf dem Steuerungsbefehle gesendet werden sollen", [ENTRY_TABLE_INPUT_INT]),
("Strom", "Schalte den Strom beim Starten der Steuerung ein", [ENTRY_TABLE_INPUT_BOOL])
] # The list called params_w_defs works like this: (parameter as bold text, explanation of the parameter, widget used to display the parameter)
    
    def __init__(self):
        EntryTable.__init__(self, self.params_w_defs, self.server_attributes, False, True)
        self.load(Config.server)

class JoystickTable(EntryTable):
    joystick_attributes = ["emergency_button", "reverse_button", "accel_axis", "focus_button", "use_auto_focus", "show_function_nr"]
    params_w_defs = [
("Nothalt", "Der Button am Gamepad, über den die Gleisspannung ausgeschaltet werden kann", [ENTRY_TABLE_INPUT_INT]),
("Richtungswender", "Der Button am Gamepad, der einen Richtungswechsel der Lokomotive bewirkt", [ENTRY_TABLE_INPUT_INT]),
("Beschleunigung", "Die Achse am Gamepad, mit der die Geschwindigkeit der Lok geregelt wird", [ENTRY_TABLE_INPUT_INT]),
("Fokus", "Der Button am Gamepad, der die zurzeit ausgewählte Lok in den im Fenster sichtbaren Bereich holt", [ENTRY_TABLE_INPUT_INT]),
("Auto-Fokus", "Die ausgewählte Lok immer fokussieren, wenn nur ein Gamepad angeschlossen ist", [ENTRY_TABLE_INPUT_BOOL]),
("Button-Nr", "Die Nummer des zugehörigen Tasters am Gamepad auf den Funktions-Buttons anzeigen", [ENTRY_TABLE_INPUT_BOOL])
] # Liste mit verständlicheren Namen für die Parameter (wird in der GUI angezeigt)
    
    def __init__(self):
        EntryTable.__init__(self, self.params_w_defs, self.joystick_attributes, False, True)
        self.load(Config.joystick)

class StandardTreeView(Gtk.TreeView): # Basisklasse für LokTreeView, LokPropertyTreeView und LocoFunctionTreeView
    def __init__(self, cell_renderers, columnnames_tooltips_renderers, column_types, name, save_method, liststore=None):
        self.column_types = column_types
        self.name = name
        self.save_method = save_method
        Gtk.TreeView.__init__(self, liststore)
        
        nr = 0
        for column_name, column_tooltip, renderer_id in columnnames_tooltips_renderers:
            label = Gtk.Label(label=column_name)
            label.show()
            label.set_tooltip_text(column_tooltip)
            column = Gtk.TreeViewColumn(None, cell_renderers[renderer_id], text=nr)
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
        
class LocoFunctionTreeView(StandardTreeView):
    column_names_tooltips_renderers = [
("Bezeichnung", "Der Name der Funktion ('Licht', 'Hupe' ...)", 0),
("Funktion", "Die Nummer der Funktion im Lok-Decoder", 0),
("Wert", "Der voreingestellte Zustand der Funktion: An oder Aus", 2),
("Gamepad-Button", "Der Button am Gamepad, dem die Lok-Funktion zugewiesen ist", 0),
("Schaltart", "Die Art, mit der eine Funktion durch einen Gamepad-Button geschaltet wird: Taster oder Umschalter", 3)
]
    column_types = [GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING, GObject.TYPE_INT, GObject.TYPE_STRING]
    
    def __init__(self):
        # self.save_status_method = save_status_method
        self.function_liststores = []
        cell_renderers = []
            
        # CellRenderer für Textfelder erzeugen
        textrenderer = Gtk.CellRendererText()    
        textrenderer.set_property("editable", True)
        textrenderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        textrenderer.connect("edited", self.new_value)
        cell_renderers.append(textrenderer)
        # CellRenderer für nicht editierbare Textfelder erzeugen
        textrenderer_not_editable = Gtk.CellRendererText()
        cell_renderers.append(textrenderer_not_editable)
        
        # CellRenderer für Combobox erzeugen
        for i in range(2): # Liste mit CellRendererCombos auffüllen
            comborenderer = Gtk.CellRendererCombo()
            comborenderer.set_property("editable", True)
            comborenderer.set_property("has-entry", False)
            comborenderer.set_property("text-column", 0)
            comborenderer.connect("edited", self.new_value)
            cell_renderers.append(comborenderer)
        
        # Comborenderer 0 aus ListStore für Wert füllen
        combostore_wert = Gtk.ListStore(GObject.TYPE_STRING)
        combostore_wert.append(["An"])
        combostore_wert.append(["Aus"])
        cell_renderers[2].set_property("model", combostore_wert)
        
        # Comborenderer 1 aus ListStore für Taster füllen
        combostore_taster = Gtk.ListStore(GObject.TYPE_STRING)
        combostore_taster.append(["Taster"])
        combostore_taster.append(["Umschalter"])
        cell_renderers[3].set_property("model", combostore_taster)    

        StandardTreeView.__init__(
            self,
            cell_renderers,
            self.column_names_tooltips_renderers,
            self.column_types,
            "LocoFunctionTreeView",
            self.save_changes)
        
        self.set_vexpand(True)
        self.set_hexpand(True)
    
    def add_liststore(self, position):
        liststore = Gtk.ListStore(*self.column_types)
        self.set_model(liststore)
        if position == -1:
            self.function_liststores.append(liststore)
        else:
            self.function_liststores.insert(position, liststore)
    
    def load(self):
        del self.function_liststores[:]
        for nr, loco in enumerate(Config.locos):
            self.function_liststores.append(Gtk.ListStore(*self.column_types))
            for function in loco.functions:
                if function.state:
                    state = "An"
                else:
                    state = "Aus"
                if function.use_push_to_make:
                    way_of_control = "Taster"
                else:
                    way_of_control = "Umschalter"
                self.function_liststores[nr].append([function.name, function.nr, state, function.button, way_of_control])
        
    def save_changes(self, path, column_nr, new_value):
        loco_id = self.function_liststores.index(self.get_model())
        if new_value == 'Taster':
            new_value = True
        elif new_value == 'Umschalter':
            new_value = False
        elif new_value == 'An':
            new_value = True
        elif new_value == 'Aus':
            new_value = False
        setattr(Config.locos[loco_id].functions[path.get_indices()[0]], Config.function_attributes[column_nr][0], new_value)
        
class LocoSelectionTreeView(StandardTreeView):
    column_names_tooltips_renderers = [
("Zu konfigurierende Lok wählen", "", 0)
]
    column_types = [GObject.TYPE_STRING]
    loco_attributes = ["name"]
    
    def __init__(self, loco_property_frame, loco_function_frame, loco_speed_frame):
        self.liststore = Gtk.ListStore(*self.column_types)
        self.loco_function_frame = loco_function_frame
        self.loco_properties_frame = loco_property_frame
        self.loco_function_treeview = self.loco_function_frame.scrolled_window.treeview
        self.loco_property_table = self.loco_properties_frame.table
        self.loco_speed_frame = loco_speed_frame
        self.loco_speed_graph = loco_speed_frame.graph
        textrenderer = Gtk.CellRendererText()
        textrenderer.set_property("editable", True)
        textrenderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        textrenderer.connect("edited", self.new_value)
        
        StandardTreeView.__init__(
            self,
            [textrenderer],
            self.column_names_tooltips_renderers,
            self.column_types,
            "LocoSelectionTreeView",
            self.save_changes,
            self.liststore)

        self.connect("cursor-changed", self.loco_selection)

    def loco_selection(self, treeview):
        path, column = self.get_cursor()
        if path == None:
            self.loco_function_treeview.set_model(None)
        else:
            row = path.get_indices()[0]
            self.loco_function_treeview.set_model(self.loco_function_treeview.function_liststores[row]) # Zugehörige Funktionenliste auswählen
            self.loco_speed_frame.notice_combo_change = False
            self.loco_property_table.load(Config.locos[row])
            self.loco_speed_frame.load(Config.locos[row])
            self.loco_speed_frame.notice_combo_change = True
        
    def new_loco(self):
        path = self.get_cursor()[0]
        if path == None:
            loco = config.Loco(Config.unsaved_changes)
            Config.locos.append(loco)
            self.loco_function_treeview.add_liststore(-1)
            new_row = self.append_loco(loco)
            self.loco_properties_frame.set_sensitive(True)
            self.loco_function_frame.set_sensitive(True)
            self.loco_speed_frame.set_sensitive(True)
        else: # if a row is selected, place loco beneath that row
            row = self.liststore.get_iter(path)
            row_nr = path.get_indices()[0]
            loco = config.Loco(Config.unsaved_changes)
            Config.locos.insert(row_nr + 1, loco)
            self.loco_function_treeview.add_liststore(row_nr + 1) # add new liststore to function_treeview
            new_row = self.liststore.insert_after(row, [getattr(loco, attrib) for attrib in self.loco_attributes]) # Nach der ausgewählten Zeile eine neue Zeile mit Standardwerten einfügen
        self.set_cursor(self.liststore.get_path(new_row), None, False)
        
    def append_loco(self, loco):
        return self.liststore.append([getattr(loco, attrib) for attrib in self.loco_attributes])
            
    def load(self):
        self.liststore.clear()
        if len(Config.locos) > 0:
            for loco in Config.locos:
                self.append_loco(loco)
            self.set_cursor(Gtk.TreePath.new_from_string("0"))
            self.loco_properties_frame.set_sensitive(True)
            self.loco_function_frame.set_sensitive(True)
            self.loco_speed_frame.set_sensitive(True)
            
    def save_changes(self, path, column_nr, new_value):
        setattr(Config.locos[path.get_indices()[0]], self.loco_attributes[column_nr], new_value)

class SpeedStepGraph(Gtk.DrawingArea):
    width = 360 # currently unimportant, cause the width is defined by the ButtonBoxLocoFunctionActions 
    height = 340
    border = 55.0 # important: border must be larger as radius_large + the width/height of the axes!
    radius_small = 3.2
    radius_large = 7.2
    drag = None
    line_color = (0.2, 0.2, 0.4)
    control_point_outer_color = (0.1686, 0.1686, 0.1686)
    control_point_inner_color = (0.804, 0.804, 0.757)
    point_color = (0.35, 0.35, 0.7216)
    axes_color = (0, 0, 0)
    legend_color = (0.1, 0.1, 0.1)
    x_legend_text = "Geschwindigkeit in km/h"
    y_legend_text = "Fahrstufe"
    x_res_list = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2.5, 5, 10, 20, 50] # list of acceptable x-resolutions
    y_res_dict = {128: 10, 28: 2, 27: 2, 14: 1} # defines the axis-resolution for different nrs of speed steps (e.g. steps of 10 for 128 speed steps)
    
    def __init__(self):
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
        
        self.popup = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        self.popup.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)
        self.popup.set_opacity(0.65)
        self.popup.label = Gtk.Label.new("")
        self.popup.add(self.popup.label)
    
    def draw(self, area, cr):
        if hasattr(self, "loco"):
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
            for y in xrange(1, self.loco.speed_steps):
                x = self.loco.speed_to_step_func.get_x(y)
                if x != None:
                    x_abs, y_abs = self.get_abs_coords(x, y)
                    cr.arc(x_abs, y_abs, self.radius_small, 0, 2 * pi)
                    cr.fill()
            cr.stroke()
        
            for nr in xrange(len(self.loco.speed_to_step_func.control_points) - 1):
                x_abs_1, y_abs_1 = self.get_abs_coords(*self.loco.speed_to_step_func.control_points[nr])
                x_abs_2, y_abs_2 = self.get_abs_coords(*self.loco.speed_to_step_func.control_points[nr + 1])
                
                cr.move_to(x_abs_1, y_abs_1)
                cr.set_source_rgb(*self.line_color)
                cr.line_to(x_abs_2, y_abs_2)
                cr.stroke()
                
                cr.set_source_rgb(*self.control_point_outer_color)
                cr.arc(x_abs_1, y_abs_1, self.radius_large, 0, 2 * pi)
                cr.fill()
                cr.set_source_rgb(*self.control_point_inner_color)
                cr.arc(x_abs_1, y_abs_1, self.radius_large - 1, 0, 2 * pi)
                cr.fill()
            
            cr.set_source_rgb(*self.control_point_outer_color)
            cr.arc(x_abs_2, y_abs_2, self.radius_large, 0, 2 * pi)
            cr.fill()
            cr.set_source_rgb(*self.control_point_inner_color)
            cr.arc(x_abs_2, y_abs_2, self.radius_large - 1, 0, 2 * pi)
            cr.fill()
            cr.stroke()
    
    def update_loco(self):
        self.loco.speed_funcs = self.loco.speed_to_step_func.func_segments
        self.loco.speed_control_points = self.loco.speed_to_step_func.control_points
    
    def get_touched_point(self, x, y):
        result = None, None
        for nr, point in enumerate(self.loco.speed_to_step_func.control_points):
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
        return self.border + x * self.x_factor, self.height - self.border - y * self.y_factor
    
    def get_speed_coords(self, x, y):
        return (x - self.border) / self.x_factor, (self.height - self.border - y) / self.y_factor
    
    def button_pressed(self, area, event):
        nr, point = self.get_touched_point(event.x, event.y)
        if nr != None:
            if event.button == 3:
                self.loco.speed_to_step_func.remove_control_point(nr)
                self.queue_draw()
                self.update_loco()
            else:
                self.drag = nr
                self.popup.set_position(Gtk.WindowPosition.MOUSE)
                self.popup.label.set_text(str("%0.2f" % point[0]) + "\n" + str("%0.2f" % point[1]))
                self.popup.show_all()
        else:
            x, y = self.get_speed_coords(event.x, event.y)
            self.loco.speed_to_step_func.add_control_point(x, y)
            self.queue_draw()
            self.update_loco()
    
    def button_released(self, area, event):
        self.drag = None
        self.popup.hide()
    
    def motion(self, area, event):
        if self.drag != None:
            x, y = self.get_speed_coords(event.x, event.y)
            if x < 0:
                x = 0
            elif x > self.loco.max_speed:
                x = self.loco.max_speed
            if y < 0:
                y = 0
            elif y > self.loco.speed_steps:
                y = self.loco.speed_steps
            old_point = self.loco.speed_to_step_func.control_points[self.drag]
            new_point = self.loco.speed_to_step_func.move_control_point(self.drag, x, y)
            self.queue_draw()
            if old_point != new_point:
                self.update_loco()
            self.popup.label.set_text(str("%0.2f" % new_point[0]) + "\n" + str("%0.2f" % new_point[1]))
                
    def create_coordinate_system(self):
        self.coordinate_system = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        c = cairo.Context(self.coordinate_system)
        c.set_line_width(2)
        y_axis_start = self.height - self.border + self.radius_large + 2
        y_axis_end = self.height - self.border + self.radius_large + 20
        x_axis_start = self.border - self.radius_large - 30
        x_axis_end = self.border - self.radius_large
        x_legend_width, x_legend_height = c.text_extents(self.x_legend_text)[2:4]
        y_legend_width, y_legend_height = c.text_extents(self.y_legend_text)[2:4]
        c.select_font_face("sans-serif")
        c.set_font_size(14)
        c.set_source_rgb(*self.legend_color)
        c.move_to(0.5 * (self.width - self.border - x_legend_width), y_axis_end + 0.5 * (self.height - y_axis_end + x_legend_height))
        c.show_text(self.x_legend_text)

        c.move_to(0.5 * (x_axis_start + y_legend_height), 0.5 * (self.height - self.border + y_legend_width))
        c.rotate(pi / -2.0)
        c.show_text(self.y_legend_text)
        c.rotate(pi / 2.0)
        c.set_font_size(12)
        c.set_source_rgb(*self.axes_color)
        
        max_width = c.text_extents(str(128))[2] # calculate highest possible width of a number-label at y-axis (obviously the width of str(128))
        estimated_res = self.loco.max_speed / 20.0
        for res in self.x_res_list: # find best resolution
            if res >= estimated_res:
                break
        pos = 0
        while pos <= self.loco.max_speed:
            text = str(pos)
            width, height = c.text_extents(text)[2:4]
            x, y = self.get_abs_coords(pos, pos)
            
            c.move_to(x, y_axis_start)
            c.line_to(x, y_axis_end - height - 3)
            c.move_to(x - 0.5 * width, y_axis_end)
            c.show_text(text)
            pos += res
        
        res = self.y_res_dict[self.loco.speed_steps]
        for pos in xrange(0, self.loco.speed_steps + res, res):
            if pos > self.loco.speed_steps:
                pos = self.loco.speed_steps
            text = str(pos)
            width, height = c.text_extents(text)[2:4]
            x, y = self.get_abs_coords(pos, pos)
            
            c.move_to(x_axis_start + max_width + 3, y)
            c.line_to(x_axis_end, y)
            c.move_to(x_axis_start + (max_width - width), y + 0.5 * height)
            c.show_text(text)
        c.stroke_preserve()
    
    def calc_size_factors(self):
        self.x_factor = (self.width - self.border - self.radius_large - 10) / float(self.loco.max_speed)
        self.y_factor = (self.height - self.border - self.radius_large) / float(self.loco.speed_steps)
    
    def load(self, loco):
        self.loco = loco
        self.calc_size_factors()
        self.create_coordinate_system()
        self.queue_draw()
        
    def clear(self):
        del self.loco
        self.queue_draw()
