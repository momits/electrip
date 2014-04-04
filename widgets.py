#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from gi.repository import GObject, Gtk, Pango, Gdk
from locked_print import locked_print
import cairo
from math import pi

from constants import ELECTRIP_VERSION
from dialog_templates import FileSetResetDialog, ImageFileFilter, \
    AllFileFilter, SoundFileFilter

class StockImageButton(Gtk.Button):
    """
    DEPRECATED - will be removed any time soon
    """
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
        
class ArrowButton(Gtk.Button):
    """
    :class:`Gtk.Button` which displays an arrow.
    If *direction* is ``True``, the arrow points
    upwards, otherwise downwards.
    """
    def __init__(self, direction):
        Gtk.Button.__init__(self)
        if direction:
            self.set_image(Gtk.Arrow.new(Gtk.ArrowType.UP,
                                         Gtk.ShadowType.NONE))
        else:
            self.set_image(Gtk.Arrow.new(Gtk.ArrowType.DOWN,
                                         Gtk.ShadowType.NONE))

class BoldLabel(Gtk.Label):
    """
    :class:`Gtk.Label` with bold font.
    """
    def __init__(self, text):
        Gtk.Label.__init__(self)
        self.set_markup("<b>" + text + "</b>")

class TopAlignment(Gtk.Alignment):
    """
    :class:`Gtk.Alignment` which aligns *child*
    to the top.
    """
    def __init__(self, child):
        Gtk.Alignment.__init__(self)
        self.set(0.0, 0.0, 0.0, 0.0)
        self.add(child)

class Frame(Gtk.Frame):
    """
    :class:`Gtk.Frame` which displays *label*
    as a :class:`BoldLabel`, if specified.
    """
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

class TreeViewActionBox(Gtk.ButtonBox):
    """
    A :class:`Gtk.ButtonBox` providing Buttons for adding, removing
    and moving rows in a :class:`Gtk.TreeView`.
    
    *treeview* is the :class:`Gtk.TreeView`-instance the
    :class:`TreeViewActionBox` should operate on.
    *add_row_label* and *remove_row_label* specify the labels displayed
    on the buttons used for adding and removing rows.
    """
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
        """
        Internal method.
        """
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
        """
        Internal method.
        """
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
        """
        Internal method.
        """
        path = treeview.get_cursor()[0]
        liststore = treeview.get_model()
        if path != None:
            self.remove_row_at(path.get_indices()[0])
            liststore.remove(liststore.get_iter(path))
            self.unsaved_changes()
        else:
            locked_print("Keine Zeile ausgewählt, "
                         "es kann nichts gelöscht werden.")
    
    def add_row_at_start(self):
        """
        Called when the user has asked the :class:`TreeViewActionBox` to add a
        new row at the start-position of the TreeView.
        Must be implemented in a child class and return a list representing
        the data in the new row. E.g. if the TreeView consists of a name- and
        a description-column, the list could be
        ``["some name", "the description"]``.
        """
        raise NotImplementedError()
    
    def add_row_beneath(self, row_nr):
        """
        Called when the user has asked the :class:`TreeViewActionBox` to add a
        new row beneath *row_nr*.
        Must be implemented in a child class and return a list representing
        the data in the new row (see :func:`add_row_at_start`).
        """
        raise NotImplementedError()
      
    def remove_row_at(self, row_nr):
        """
        Called when the :class:`TreeViewActionBox` has removed the
        row with *row_nr*. Must be implemented in a child class to force it to
        update its datamodel.
        """
        raise NotImplementedError()
    
    def move_row_up(self, row_nr):
        """
        Called when the :class:`TreeViewActionBox` has moved the
        row with *row_nr* one position upwards (*row_nr* - 1).
        Must be implemented in a child class to force it to
        update its datamodel.
        """
        raise NotImplementedError()
    
    def move_row_down(self, row_nr):
        """
        Called when the :class:`TreeViewActionBox` has moved the
        row with *row_nr* one position downwards (*row_nr* + 1).
        Must be implemented in a child class to force it to
        update its datamodel.
        """
        raise NotImplementedError()
        
    def unsaved_changes(self):
        """
        Called whenever changes were made to the data in the TreeView
        (reordering, deleting rows etc.).
        Allows child classes to get notified when these changes occur.
        Must not necessarily be implemented.
        """

class EasyComboBox(Gtk.ComboBox):
    """
    A simplified :class:`Gtk.ComboBox` using a simple
    python-style data-model.
    *content_type* specifies the type of the values
    to be stored in the combobox
    (e.g. :class:`GObject.TYPE_STRING`, ...).
    *mapping* is a list of 2-tuples, which maps values
    stored in the  model (referred to as *model_values*)
    to the displayed values (referred to as *disp_values*).
    Example: see :class:`EntryTable`.
    """
    def __init__(self, content_type, mapping): 
        Gtk.ComboBox.__init__(self)
        self.mapping = mapping
        liststore = Gtk.ListStore(content_type)
        for unused_saved_val, disp_val in mapping:
            liststore.append([disp_val])
        self.set_model(liststore)
        
        renderer = Gtk.CellRendererText()
        self.pack_start(renderer, True)
        self.add_attribute(renderer, "text", 0)
        self.set_active(0)

    def retrieve_value(self):
        """
        Returns the *model_value* for the datamodel according to the
        currently active item.
        """
        displayed_value = self.get_model()[self.get_active()][0]
        for saved_val, disp_val in self.mapping:
            if displayed_value == disp_val:
                return saved_val
            
    def retrieve_disp_value(self):
        """
        Returns the *disp_value* which is currently displayed.
        """
        return self.get_model()[self.get_active()][0]
        
    def set_value(self, model_value):
        """
        Makes the EasyComboBox display the *disp_value* that belongs
        to *model_value*.
        """
        model_value_correct = False
        for saved_val, disp_val in self.mapping:
            if model_value == saved_val:
                for row_nr, row in enumerate(self.get_model()):
                    if disp_val in row:
                        self.set_active(row_nr)
                        model_value_correct = True
                        break
                break
        if not model_value_correct:
            self.set_active(0)
            value = self.retrieve_value()
            locked_print("Dateiformat inkorrekt: Unbekannter Wert '" +
                         str(model_value) +
                         "', verwende Standardwert '" +
                         str(value) + "'")
            # report we changed the value to the default
            self.emit("changed")

class EasyFileButton(Gtk.Bin):
    """
    A simplified :class:`Gtk.FileChooserButton` (opens a
    file-selection-dialog when clicked).
    *file_filters* is a list of :class:`Gtk.FileFilter`-objects
    used to filter the displayed files in the dialog, the first
    filter in the list is the default. 
    """
    
    __gsignals__ = {
      "file-set": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
    
    # FIXME: it must be possible to reset the selection
    # to 'None'
    
    def __init__(self, file_filters=[]):
        # we fake a subclass of Gtk.FileChooserButton
        # to be able to use our own dialog
        Gtk.Bin.__init__(self)
        dialog = FileSetResetDialog()
        if len(file_filters) > 0:
            for file_filter in file_filters:
                dialog.add_filter(file_filter)
            dialog.set_filter(file_filters[0])
        dialog.connect("response", self.check_reset)
        self.button = Gtk.FileChooserButton.new_with_dialog(dialog)
        self.add(self.button)
        
    def check_reset(self, unused_button, response_id):
        if response_id == 2:
            self.set_value(None)
        
    def retrieve_value(self):
        """
        Returns the currently selected file.
        """
        return self.button.get_filename()
    
    def set_value(self, path):
        """
        Makes the :class:`EasyFileButton` point to the file located
        at *path*.
        """
        if path != None:
            self.button.set_filename(path)
        else:
            # TODO: find out how to reset the filename to "None"
            self.button.set_filename("(keine)")
            self.emit("file-set")
    
class EasyVolumeButton(Gtk.VolumeButton):
    """
    A simplified :class:`Gtk.VolumeButton`, emits the
    *volume-set*-signal if its value changes.
    Does also provide the ``set_value`` and ``retrieve_value``-
    methods.
    """
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
    """
    Provides a UI to set attributes on
    configuration objects. Allows you to stop caring
    about signal-handling and layout.
    
    If *use_tooltips* is ``True``, the descriptions are
    provided as tooltips. Otherwise the description will
    appear behind the ui-elements.
    If *use_bold_labels* is ``True``, the labels for the
    object-attributes appear in bold font.
    
    New input-elements can be added using the
    'add_(some_element)'-methods, where the first two arguments
    specify the *label* and the *description*-text for the
    respective attribute.
    
    Have a look at the following example::
    
        # NOTE: we assume a Loco-instance called 'loco'
        # has already been created
        
        # choose layout-options on creation
        table = EntryTable(True, False)
        
        # add a combo-box which operates on loco.protocol
        table.add_combo_entry("Protokoll",
                              "Das Digitalprotokoll, welches"
                              "vom Decoder verwendet wird.",
                              "protocol",
                              GObject.TYPE_STRING,
                              (("M 1", "Märklin Motorola Version 1"),
                               ("M 2", "Märklin Motorola Version 2"),
                               ("N 1", "DCC kurzes Adressformat"),
                               ("N 2", "DCC langes Adressformat")))
        
        # you can add more ui-elements for different attributes 
        table.add_...
        
        # load the protocol value from loco
        # and the others you have specified
        table.load(loco)
        
        # now, if the user selects "Märklin Motorola Version 1",
        # "M 1" will be stored in loco.protocol
    """
    def __init__(self,
                 use_tooltips,
                 use_bold_labels,
                 orientation=Gtk.Orientation.VERTICAL,
                 end=None):
        Gtk.Grid.__init__(self)
        
        self.set_column_spacing(10)
        self.set_row_spacing(5)
        self.set_border_width(6)
        
        self.use_tooltips = use_tooltips
        self.use_bold_labels = use_bold_labels
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
        if self.use_bold_labels:
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
        Adds a :class:`Gtk.Entry`.
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
        Adds a :class:`Gtk.SpinButton`.
        
        *min_value* and *max_value* specify the value range for
        the integer.
        *step* specifies the step between two possible values.
        *step* must not be an integer, but the values will be
        converted to integers before being stored.
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
        Adds a :class:`Gtk.SpinButton` for floats.
        
        *min_value* and *max_value* specify the value range for
        the float.
        *step* specifies the precision of the number as step
        between two possible values.
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
        Adds a :class:`EasyComboBox`.
        
        *content_type* specifies the type of the values
        to be stored in the combobox
        (e.g. :class:`GObject.TYPE_STRING`, ...).
        *mapping* is a list of 2-tuples, which maps values
        stored in the  model to the displayed values.
        Example: see :class:`EntryTable`.
        """
        combo = EasyComboBox(content_type, mapping)
        combo.connect("changed",
                      self.save_changes,
                      config_attribute)
        self.attach_entry_widget(combo, label, description, config_attribute)
        
    def add_sound_file_entry(self, label, description, config_attribute):
        """
        Adds an :class:`EasyFileButton` for sound-file selection.
        """
        file_button = EasyFileButton([SoundFileFilter(), AllFileFilter()])
        file_button.connect("file-set",
                            self.save_changes,
                            config_attribute)
        self.attach_entry_widget(file_button, label, description, config_attribute)
        
    def add_image_file_entry(self, label, description, config_attribute):
        """
        Adds an :class:`EasyFileButton` for image-file selection.
        """
        file_button = EasyFileButton([ImageFileFilter(),
                                      AllFileFilter()])
        file_button.connect("file-set",
                            self.save_changes,
                            config_attribute)
        self.attach_entry_widget(file_button, label, description, config_attribute)
        
    def add_bool_entry(self, label, description, config_attribute):
        """
        Adds a :class:`Gtk.CheckButton` for boolean values.
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
        Adds an :class:`EasyVolumeButton`.
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
        Adds a :class:`Gtk.Button` with *button_label*
        which calls *callback* when clicked.
        """
        button = Gtk.Button(button_label)
        button.connect("clicked", callback)
        self.attach_entry_widget(button, label, description)
        
    def add_label(self, label, description, markup):
        """
        Adds a Label with a text according to *markup*.
        """
        label_widget = Gtk.Label()
        label_widget.set_markup(markup)
        self.attach_entry_widget(label_widget, label, description)
            
    def load(self, config_object):
        """
        Loads the values for the user interface elements from
        *config_object*.
        """
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
        """
        Transports changes from the user-interface to the
        ``EntryTable.config_object`` which was set using
        :func:`EntryTable.load`.
        This method is called automatically whenever the user
        changes an element which was added using one of the
        'add_(some_element)'-methods.
        """
        if config_attrib != None:
            value = widget.retrieve_value()
            # only set attributes when they differ from what is already saved
            # -> prevent signal-handler trouble on loading
            if getattr(self.config_object, config_attrib) != value:
                setattr(self.config_object, config_attrib, value)

class ScrolledTreeView(Gtk.ScrolledWindow):
    """
    A :class:`Gtk.ScrolledWindow` which embeds a
    :class:`Gtk.TreeView`.
    """
    def __init__(self, treeview):
        Gtk.ScrolledWindow.__init__(self)
        self.set_policy(Gtk.PolicyType.AUTOMATIC,
                        Gtk.PolicyType.AUTOMATIC)
        self.treeview = treeview
        natural_req = self.treeview.get_preferred_size()[1]
        self.set_size_request(natural_req.width,
                              natural_req.height + 40)
        self.add(self.treeview)
        

# Base-class for TreeViews
class TreeView(Gtk.TreeView):
    """
    A simplified TreeView, allowing to easily add columns
    and transport changes back to a datamodel.
    
    *name* specifies the name of the TreeView, used for the
    'unsaved-changes'-messages.
    
    Example::
    
        class CustomTreeView(TreeView):
            def __init__(self):
                widgets.TreeView.__init__(self, "CustomTreeView")
                self.add_text_colum("Name of the column",
                                    "A nice column",
                                    GObject.TYPE_STRING)
                self.add_non_editable_text_colum("Sound file",
                                                 "The sound to be played "
                                                 "('*.wav' or '*.ogg')",
                                                 GObject.TYPE_STRING)
                # self.add_more_stuff ...
                self.update_model()
                
                # we can connect to double-clicks as follows:
                # (assuming we created a handler 'choose_sound')
                self.connect("row-activated", self.choose_sound)
    """
    def __init__(self, name):
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
        Adds a new column using *cell_renderer*.
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
        Adds a column with editable text.
        The *column_name* is displayed above the column
        and the *column_tooltip* appears when the mouse hovers
        over the colums header.
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
        Adds a column with non-editable text.
        For arguments, see :func:`add_text_column`.
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
        Adds a column with :class:`Gtk.ComboBox`-widgets.
        
        For *column_name* and *column_tooltip* see
        :func:`add_text_column`.
        *content_type* defines the type of the values
        to be stored in the combobox (e.g. str, float ...).
        *values* is a list of the values the user can
        choose from.
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
            
    def save_changes(self, path, column_nr, new_value):
        """
        This method is called whenever a value of a cell
        in the TreeView has changed. Child classes should
        make use of this.
        
        *path*: a :class:`Gtk.TreePath` to the respective cell.
        *column_nr*: number of the column where the change occured
        *new_value*: the new value of the cell
        """
        raise NotImplementedError()


class CustomHandlePaned(Gtk.Paned):
    """
    A :class:`Gtk.Paned` with ``30px`` height.
    Can be accessed via CSS using the name
    'custom-handle-paned'.
    """
    def __init__(self):
        Gtk.Paned.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_name("custom-handle-paned")
        self.set_hexpand(True)
        # Attention: these values only fit to the shipped handle-icon!
        self.set_size_request(-1, 30)

        
class PopupButton(Gtk.Button):
    """
    A :class:`Gtk.Button` which opens a :class:`Popup`-window.
    The buttons label is *text* and it appears bold if *use_bold*
    is ``True``. *popup* specifies the :class:`Popup`-instance
    to be used.
    """
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

class Popup(Gtk.Window):
    """
    A :class:`Gtk.Window` which hides itself if closed, instead
    of being destroyed. It tries to be transient for the
    *main_window* and asks the window-manager to be displayed
    like a tooltip.
    """
    def __init__(self, main_window, title="",
                 type_hint=Gdk.WindowTypeHint.TOOLTIP):
        Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
        self.set_title("Electrip " + ELECTRIP_VERSION + " - " + title)
        self.connect("delete-event", self.delete_event)
        if type_hint != None:
            self.set_type_hint(type_hint)
        self.main_window = main_window
        
    def show_at_mouse(self):
        """
        Shows the popup and its contents at the current
        position of the mouse-pointer.
        """
        self.set_position(Gtk.WindowPosition.MOUSE)
        self.set_transient_for(self.main_window)
        self.show_all()
        
    def show_at_center(self):
        """
        Shows the popup and its contents at the center
        of the screen.
        """
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_transient_for(self.main_window)
        self.show_all()
    
    # can be called multiple times
    def set_content(self, widget):
        """
        Sets the content-widget of the popup
        to *widget*. Multiple calls will result in
        the removal of the prior widget.
        """
        if hasattr(self, "content"):
            self.remove(self.content)
        self.resize_to_geometry(1, 1)
        self.content = widget
        self.add(self.content)
        
    def delete_event(self, window, event):
        self.hide()
        return True


class ControlPointGraph(Gtk.DrawingArea):
    """
    Graph-widget allowing to edit a :class:`LinearSegmentFunction`
    visually in a cartesian coordinate system.
    *x_legend_text* and *y_legend_text* specify the labels for the
    x- and y-axis.
    *x_res_list* and *y_res_list* are lists containing acceptable
    resolutions for the x- and y-axis.
    
    Behaviour:
    
        * **Left-click**: Creates a new control-point
        * **Left-click + drag**: Drags an existing control-point
        * **Right-click**: Removes an existing control-point
    """
    def __init__(self,
                 x_legend_text,
                 y_legend_text,
                 x_res_list,
                 y_res_list):
        self.x_legend_text = x_legend_text
        self.y_legend_text = y_legend_text
        self.x_res_list = x_res_list
        self.y_res_list = y_res_list
        
        # default colors
        self.line_color = (0.2, 0.2, 0.4)
        self.control_point_outer_color = (0.1686, 0.1686, 0.1686)
        self.control_point_inner_color = (0.804, 0.804, 0.757)
        self.point_color = (0.35, 0.35, 0.7216)
        self.axes_color = (0, 0, 0)
        self.legend_color = (0.1, 0.1, 0.1)
        
        # default dimensions
        self.width = 550
        self.height = 340
        # important: border_left_bottom must be larger than
        # radius_large + the width/height of the axes!
        self.border_left_bottom = 60.0
        self.border_right = 10
        self.coordinate_line_length = 7
        self.axis_distance = 2
        self.radius_small = 3.6
        self.radius_large = 7.3
        self.control_point_border_width = 1.3
        self.min_label_distance = 7
        self.drag = None
        
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
                self.update_config_object(self.func)
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
            self.update_config_object(self.func)
            
    def update_config_object(self, func):
        """
        Child classes must use this method to update their data-model
        to be in sync with the changed :class:`LinearSegmentFunction` *func*.
        """
        raise NotImplementedError()
    
    def button_released(self, area, event):
        if self.drag != None:
            self.update_config_object(self.func)
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
        """
        Clears the graph, removing all references
        to the function which was displayed.
        """
        # all attribs must be set at once in get_func_data,
        # so we only need to check if one of them exists
        if hasattr(self, "func"):
            del self.func
            del self.x_max
            del self.y_max
        self.queue_draw()
        
    def get_func_data(self, config_object):
        """
        Method which knows how to extract
        the relevant graph_data from a *config_object*.
        Must return 3-tuple of the form:
        ``(x_max, y_max, func)`` where x/y_max
        specify the range of the x/y-axis and
        func is the :class:`LinearSegmentFunction`
        used to display the graph.
        """
        raise NotImplementedError()
        
    def load(self, config_object):
        """
        Loads the graph using *config_object*. Requires
        :func:`get_func_data` to be overridden by a child class.
        """
        self.x_max, self.y_max, self.func = self.get_func_data(config_object)
        self.calc_size_factors()
        self.create_coordinate_system()
        self.queue_draw()
