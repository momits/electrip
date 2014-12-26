#!/usr/bin/env python
# -*- coding: UTF 8 -*-

import json
from os.path import basename, split, exists, sep as os_sep
import zipfile
from copy import deepcopy

from electrip.concurrent import locked_print
from electrip.config.loco import Loco
from electrip.config.loco_functions import ToggleMode, DecoderFunction, \
    FunctionSound, EventSound
from electrip.config.server import Server
from electrip.config.joystick import Joystick
from electrip.config.sound import Sound
from electrip.config.sound_segments import create_sound_segment
from electrip.config.sound_engines import create_engine, EngineType
from electrip.config.linear_segment_function import LinearSegmentFunction


class DictWrapper:
    """
    Wrapper used to retrieve values from
    a dictionary.
    """
    @staticmethod
    def get(d, k):
        """
        Returns the element from *d*
        with key *k*.
        """
        return d[k]
    
    @staticmethod
    def has_key(d, k):
        """
        Checks if *d* has a key named *k*.
        """
        return k in d
    
    @staticmethod
    def set(d, k, v):
        """
        Sets the element in *d*
        with key *k* to *v*.
        """
        d[k] = v
        
    @staticmethod
    def get_param_list(config_dict,
                       attribute_list,
                       ignore=False):
        return JsonModel.get_param_list_from_dict(config_dict,
                                                  attribute_list,
                                                  ignore)


class ObjectWrapper:
    """
    Wrapper used to retrieve values from
    an object.
    """
    @staticmethod
    def get(o, a):
        """
        Returns the attribute of *o*
        named *a*.
        """
        return getattr(o, a)
    
    @staticmethod
    def has_key(o, a):
        """
        Checks if *o* has an attribute
        named *a*.
        """
        return hasattr(o, a)
    
    @staticmethod
    def set(o, a, v):
        """
        Sets the attribute of *o*
        named *a* to *v*.
        """
        setattr(o, a, v)
    
    @staticmethod
    def get_param_list(obj, attributes, unused_ignore=False):
        return JsonModel.get_param_list_from_object(obj, attributes)


class JsonModel:
    """
    | Object-tree representing all the data needed by Electrip.
    | Able to load and save itself from/to Json-files.
    
    Stores several attribute-lists, which are lists of tuples
    of the form ``[("attribute_name", default_value), ...]``.
    Each attribute-list maps to an object in the configuration:
    
        * self.loco_attributes -> :class:`Loco`
        * self.engine_attributes -> :class:`Engine`
        * self.event_sound_attributes  -> :class:`EventSound`
        * self.function_sound_attributes -> :class:`FunctionSound`
        * self.segment_attributes -> :class:`SoundSegment`
        * self.function_attributes -> :class:`Function`
        * self.server_attributes -> :class:`Server`
        * self.joystick_attributes -> :class:`Joystick`
        * self.sound_attributes -> :class:`Sound`
    
    The Object-tree looks similar to this::
    
        JsonModel
            |
            |- locos
            |     |- Loco
            |     |    |- name = "V 200"
            |     |    |- image = "/home/user/V200.png"
            |     |    |- engine = ...
            |     |    |- ...
            |     |
            |     |- Loco
            |     |    |- ...
            |     |- ...
            |
            |- server
            |     |- host = "localhost"
            |     |- port = 4303
            |     |- ...
            |
            |- joystick
            |     |- emergency_button = 0
            |     |- accel_axis = 2
            |     |- ...
            |- ...   
    """
    def __init__(self, locos=None, server=None, joystick=None, sound=None):
        """
        Creates an empty object tree, or uses the passed arguments *loco*,
        *server*, *joystick* and *sound*.
        """
        self.notice_unsaved_changes = False
        self.has_unsaved_changes = False
        self.opened_file = None
        
        self.loco_attributes = [("name", "Unbenannte Lok"),
                                ("speed_steps", 128),
                                ("max_speed", 100.0),
                                ("address", 1),
                                ("protocol", "N 1"),
                                ("accel_duration", 11.5),
                                ("decel_duration", 8.5),
                                ("direction", True),
                                ("img_path", None),
                                ("sound_volume", 0)]
        
        self.engine_attributes = {"diesel":
                                  [("type", "diesel"),
                                   ("start_sound", None),
                                   ("idle_sound", None),
                                   ("quit_sound", None)],
                                  "steam":
                                  [("type", "steam"),
                                   ("idle_sound", None),
                                   ("cylinder_steam_sound", None),
                                   ("nr_strokes", 4),
                                   ("stroke_start_delay", 2.0),
                                   ("wheel_diameter", 1.2),
                                   ("min_freq", 0.2)]}
        
        self.event_sound_attributes = [("name", ""),
                                       ("state", True),
                                       ("button", 0),
                                       ("file_path", None),
                                       ("direction", None),
                                       ("min_speed", None),
                                       ("max_speed", None),
                                       ("min_accel", None),
                                       ("max_accel", None),
                                       ("fade_in", 0),
                                       ("fade_out", 0),
                                       ("play_to_end", False)]
        
        self.function_sound_attributes = [("name", ""),
                                          ("file_path", None),
                                          ("state", False),
                                          ("button", 0),
                                          ("toggle_mode", ToggleMode.TAP)]
        
        self.segment_attributes = {"diesel":
                                   [("start", 0),
                                    ("end", 100),
                                    ("load_sound", None),
                                    ("idle_sound", None),
                                    ("accel_sound", None),
                                    ("decel_sound", None)],
                                   "steam":
                                   [("start", 0),
                                    ("end", 100),
                                    ("stroke_sounds", None)]}
        
        self.function_attributes = [("name", ""),
                                    ("nr", 0),
                                    ("state", False),
                                    ("button", 0),
                                    ("toggle_mode", ToggleMode.SWITCH)]
        
        self.server_attributes = [("host", "localhost"),
                                  ("port", 4303),
                                  ("bus", 1),
                                  ("power", True)]
        
        self.joystick_attributes = [("emergency_button", 0),
                                    ("reverse_button", 1),
                                    ("accel_axis", 2),
                                    ("axis_threshold", 0.06),
                                    ("focus_button", 3),
                                    ("sound_button", 4),
                                    ("use_auto_focus", True),
                                    ("show_function_nr", False)]
        
        self.sound_attributes = [("sampling_rate", 44100),
                                 ("show_level_bar", True)]
    
        if locos is None:
            self.locos = []
        else:
            self.locos = locos
        if server is None:
            self.server = Server(self.unsaved_changes)
        else:
            self.server = server
        if joystick is None:
            self.joystick = Joystick(self.unsaved_changes)
        else:
            self.joystick = joystick
        if sound is None:
            self.sound = Sound(self.unsaved_changes)
        else:
            self.sound = sound
        # loco that is currently configured
        self.active_loco = None
        
        try:
            f = open("last_file.json")
            self.last_file = json.load(f)["last_file"]
            f.close()
        except IOError:
            self.last_file = ""
            locked_print("Noch kein letzter Dateipfad gespeichert.")
            
    @staticmethod
    def get_utf8_bytestring(value):
        """
        Returns a utf8-bytestring made from
        a unicode-object *value*. If *value* is not
        a unicode-object, *value* is returned.
        """
        if isinstance(value, unicode):
            value = value.encode("utf-8")
        return value
            
    def add_file_to_zip(self, zip_file, file_path, dest=""):
        """
        Adds a file located at *file_path* to *zip-file*,
        placing it at the subdirectory *dest*.
        Example::
        
            self.add_file_to_zip(self,
                                 zip_file,
                                 "/home/user/image.gif")
            self.add_file_to_zip(self,
                                 zip_file,
                                 "/home/user/test.wav",
                                 "sound")
            # Will place 'image.gif' in the root
            # directory of zip_file and 'test.wav' in the
            # subdirectory '/sound'
        """
        try:
            file_name = basename(file_path)
            if dest != "":
                file_name = dest + os_sep + file_name
            if file_name not in zip_file.namelist():
                zip_file.write(file_path, file_name)
        # error occurs if file_path is None (type of error
        # varies on different platforms)
        except:
            locked_print("Ungültige Datei '" + str(file_path) + 
                         "' konnte nicht in Lok-Verzeichnis kopiert werden.")
            return None
        else:
            return file_name
        
    def add_files_to_zip(self,
                         zip_file,
                         config_object,
                         attribs,
                         dest=""):
        """
        Adds multiple files to *zip_file*, where *attribs*
        is a list of attributes of *config_object* which
        should be used for the file locations.
        See :func:`add_file_to_zip`.
        Example::
        
            self.add_files_to_zip(self,
                                  zip_file,
                                  segment,
                                  ["load_sound",
                                   "accel_sound",
                                   "decel_sound",
                                   "idle_sound"])
            # Will add the files located at
            # segment.load_sound, segment.accel_sound, ...
            # to 'zip_file'
        """
        for attrib in attribs:
            if hasattr(config_object, attrib):
                file_path = getattr(config_object, attrib)
                file_name = self.add_file_to_zip(zip_file,
                                                 file_path,
                                                 dest)
                setattr(config_object, attrib, file_name)
        
    def save_loco(self, loco, dir_path):
        """
        Exports *loco* to a zip-file, including all sound-
        and image-files needed. This standalone package is
        placed in *dir_path*, named like ``loco.name``.
        """
        file_path = dir_path + os_sep + loco.name + ".zip"
        with zipfile.ZipFile(file_path,
                             "w",
                             zipfile.ZIP_DEFLATED,
                             True) as zip_file:
            save_status_method = self.new_unsaved_changes_method
            # remove any references to GObjects, as they are not copyable
            del self.new_unsaved_changes_method
            self.notice_unsaved_changes = False
            loco = self.create_loco(loco,
                                    ObjectWrapper,
                                    None)
            if loco.engine != None:
                if loco.engine.type == EngineType.STEAM:
                    for segment in loco.engine.sound_segments:
                        segment.stroke_sounds = [self.add_file_to_zip(zip_file,
                                                                      stroke_sound,
                                                                      "sound")
                                                 for stroke_sound in segment.stroke_sounds]
                    self.add_files_to_zip(zip_file, loco.engine, ["idle_sound",
                                                                  "cylinder_steam_sound"],
                                          "sound")
                    
                elif loco.engine.type == EngineType.DIESEL:
                    for segment in loco.engine.sound_segments:
                        self.add_files_to_zip(zip_file,
                                              segment,
                                              ["load_sound",
                                               "idle_sound",
                                               "accel_sound",
                                               "decel_sound"],
                                              "sound")
                    self.add_files_to_zip(zip_file,
                                          loco.engine,
                                          ["start_sound",
                                           "idle_sound",
                                           "quit_sound"],
                                          "sound")
                    
                for sound in loco.event_sounds:
                    sound.file_path = self.add_file_to_zip(zip_file,
                                                           sound.file_path,
                                                           "sound")
                        
            for sound in loco.function_sounds:
                sound.file_path = self.add_file_to_zip(zip_file,
                                                       sound.file_path,
                                                       "sound")
            
            loco.img_path = self.add_file_to_zip(zip_file,
                                                 loco.img_path,
                                                 "image")
            # write loco-config file
            zip_file.writestr(loco.name + ".loco",
                              json.dumps(self.create_loco_dict(loco),
                                         indent=2))
            locked_print("Lok wurde gespeichert in", file_path)
            self.new_unsaved_changes_method = save_status_method
            self.notice_unsaved_changes = True
        
    def create_loco_dict(self, loco):
        """
        Returns a dictionary-representation of the
        object-tree in *loco*. This is needed to save the
        loco in the Json-format.
        """
        loco_dict = self.create_dict(loco,
                                     self.loco_attributes)
        loco_dict["speed_control_points"] = loco.speed_to_step_func.control_points
        loco_dict["function_sounds"] = [self.create_dict(function_sound,
                                                         self.function_sound_attributes)
                                        for function_sound in loco.function_sounds]
        loco_dict["event_sounds"] = [self.create_dict(event_sound,
                                                      self.event_sound_attributes)
                                     for event_sound in loco.event_sounds]
        
        if loco.engine:
            engine_dict = self.create_dict(loco.engine,
                                           self.engine_attributes[loco.engine.type])
            if loco.engine.sound_segments != None:
                engine_dict["sound_segments"] = [self.create_dict(segment,
                                                                  self.segment_attributes[segment.type])
                                                 for segment in loco.engine.sound_segments]
            else:
                engine_dict["sound_segments"] = None
            loco_dict["engine"] = engine_dict
        else:
            loco_dict["engine"] = None
        function_list = [self.create_dict(function,
                                          self.function_attributes)
                         for function in loco.functions]
        loco_dict["functions"] = function_list
        return loco_dict
        
    def save(self, file_path):
        """
        Saves the current object-tree to the Json-file
        specified by *file_path*.
        """
        Config = {"locos": [self.create_loco_dict(loco) for loco in self.locos],
                  "server": self.create_dict(self.server,
                                             self.server_attributes),
                  "joystick": self.create_dict(self.joystick,
                                               self.joystick_attributes),
                  "sound": self.create_dict(self.sound,
                                            self.sound_attributes)}
        
        f = open(file_path, "w")
        json.dump(Config, f, indent=2)
        f.close()
            
        self.has_unsaved_changes = False
        self.save_opened_file(file_path)
        locked_print("Einstellungen wurden gespeichert in " + file_path)
        
    def create_dict(self, config_object, attribute_list):
        """
        Returns a dictionary-representation of *config_object*,
        using the attributes from *attribute_list*. *attribute_list*
        is a list of tuples of the form
        ``[("attribute_name", default_value), ...]``.
        The default values are not used in this method.
        """
        obj_dict = {}
        for attrib in attribute_list:
            try:
                obj_dict[attrib[0]] = getattr(config_object, attrib[0])
            # needed for objects where we don't know if they have a
            # certain attribute (e.g. sound_segments)
            except AttributeError:
                pass
        return obj_dict
    
    def set_absolute_path(self, path_prefix, config_object, attribs):
        """
        Appends *path_prefix* to all attributes in the list *attribs* 
        of *config_object*. Used to change a relative path to
        an absolute path.
        """
        for attrib in attribs:
            file_name = getattr(config_object, attrib)
            if file_name != None and exists(path_prefix + file_name):
                setattr(config_object, attrib, path_prefix + file_name)
            else:
                setattr(config_object, attrib, file_name)
    
    def load_loco(self, file_path):
        """
        Returns a :class:`Loco`-object which is
        unpacked from a zip-file-package.
        See :func:`save_loco`.
        """
        dir_path, file_name = split(file_path)
        loco_name, ending = file_name.split(".")
        if ending == "zip":
            dir_path += os_sep + loco_name + os_sep
            with zipfile.ZipFile(file_path, "r") as zip_file:
                zip_file.extractall(dir_path)
        else:
            dir_path += os_sep
            
        with open(dir_path + loco_name + ".loco") as loco_file:
            loco_dict = json.load(loco_file)
            loco = self.create_loco(loco_dict,
                                    DictWrapper,
                                    self.unsaved_changes)
            
            for sound in loco.event_sounds:
                    self.set_absolute_path(dir_path,
                                           sound,
                                           ["file_path"])
            
            if loco.engine != None:
                if loco.engine.type == EngineType.STEAM:
                    for segment in loco.engine.sound_segments:
                        segment.stroke_sounds = [dir_path + stroke_sound
                                                 for stroke_sound in segment.stroke_sounds
                                                 if stroke_sound != None]
                    self.set_absolute_path(dir_path,
                                           loco.engine,
                                           ["idle_sound",
                                            "cylinder_steam_sound"])
                    
                elif loco.engine.type == EngineType.DIESEL:
                    for segment in loco.engine.sound_segments:
                        self.set_absolute_path(dir_path,
                                               segment,
                                               ["load_sound",
                                                "idle_sound",
                                                "accel_sound",
                                                "decel_sound"])
                    self.set_absolute_path(dir_path,
                                           loco.engine,
                                           ["start_sound",
                                            "idle_sound",
                                            "quit_sound"])
                    
            for sound in loco.function_sounds:
                self.set_absolute_path(dir_path,
                                       sound,
                                       ["file_path"])
                
            self.set_absolute_path(dir_path,
                                   loco,
                                   ["img_path"])
            return loco

    def create_loco(self, loco_obj, wrapper, unsaved_changes_method):
        """
        This method covers the logic to create a new :class:`Loco`-object.
        Depending on the situation, one may want to use different data-types
        for this operation. This is specified by *wrapper*, which must be
        one of :class:`DictWrapper` or :class:`ObjectWrapper`.
        E.g. if you want to create a new Loco using an existing Loco,
        you could do this::
        
            new_loco = self.create_loco(existing_loco,
                                        ObjectWrapper,
                                        self.unsaved_changes)
        
        *unsaved_changes_method* defines the method to be called if
        an attribute on the new loco changes, usually this is
        ``Config.unsaved_changes``.
        
        Returns: The new :class:`Loco`
        """
        functions = []
        for function_obj in wrapper.get(loco_obj, "functions"):
            # old file format has no attrib 'toggle_mode', but bool 'use_push_to_make'
            if not wrapper.has_key(function_obj, "toggle_mode"):
                if wrapper.get(function_obj, "use_push_to_make"):
                    wrapper.set(function_obj, "toggle_mode", ToggleMode.PUSH)
                else:
                    wrapper.set(function_obj, "toggle_mode", ToggleMode.SWITCH)
            functions.append(DecoderFunction(unsaved_changes_method,
                                      *wrapper.get_param_list(function_obj, self.function_attributes)))
        speed_func = LinearSegmentFunction()
        if wrapper == DictWrapper:
            speed_func.load(map(tuple,
                                wrapper.get(loco_obj,
                                            "speed_control_points")))
        else:
            speed_func.load(wrapper.get(wrapper.get(loco_obj,
                                                    "speed_to_step_func"),
                                        "control_points"))
        
        if wrapper.has_key(loco_obj, "function_sounds"):
            function_sounds = [FunctionSound(unsaved_changes_method,
                                             *wrapper.get_param_list(function_sound_obj,
                                                             self.function_sound_attributes))
                               for function_sound_obj in wrapper.get(loco_obj,
                                                                     "function_sounds")]
        else:
            function_sounds = None
        
        if wrapper.has_key(loco_obj, "event_sounds"):
            if wrapper.get(loco_obj, "event_sounds") != None:
                event_sounds = [EventSound(unsaved_changes_method,
                                              *wrapper.get_param_list(event_sound_obj,
                                                                      self.event_sound_attributes))
                                   for event_sound_obj in wrapper.get(loco_obj,
                                                                      "event_sounds")]
        else:
            try:
                # until v5.0.8 event sounds were stored in the engine
                event_sounds = [EventSound(unsaved_changes_method,
                                           *wrapper.get_param_list(event_sound_obj,
                                                                   self.event_sound_attributes))
                                for event_sound_obj in wrapper.get(wrapper.get(loco_obj,
                                                                               "engine"),
                                                                   "event_sounds")]
            except:
                event_sounds = None
        
        if  wrapper.has_key(loco_obj, "engine") \
        and wrapper.get(loco_obj, "engine") != None:
            engine_obj = wrapper.get(loco_obj, "engine")
            param_list = wrapper.get_param_list(engine_obj,
                                        self.engine_attributes[wrapper.get(engine_obj,
                                                                           "type")])
            param_list.insert(1, unsaved_changes_method)
            if wrapper.get(engine_obj, "sound_segments") != None:
                try:
                    # deepcopy(param) copies the attributes of the sound-segments
                    # to make sure the 'nr_strokes'-list of SteamSoundSegment
                    # is not passed by reference (causes pygame.Sound-objects lying
                    # in memory after switching back from control to configuration)
                    sound_segments = [create_sound_segment(wrapper.get(engine_obj, "type"),
                                                           unsaved_changes_method,
                                                           *[deepcopy(param)
                                                             for param in wrapper.get_param_list(segment_obj,
                                                                self.segment_attributes[wrapper.get(engine_obj, "type")],
                                                                True)])
                                      for segment_obj in wrapper.get(engine_obj,
                                                                     "sound_segments")]
                except KeyError:
                    locked_print("Die Datei besitzt noch keine "
                                 "Geräusch-Informationen.")
                    sound_segments = None
            else:
                sound_segments = None
            param_list.append(sound_segments)
            engine = create_engine(*param_list)
        else:
            engine = None
        
        return Loco(unsaved_changes_method,
                    functions,
                    speed_func,
                    function_sounds,
                    event_sounds,
                    engine,
                    *wrapper.get_param_list(loco_obj, self.loco_attributes))

    def load(self, file_path):
        """
        Loads the object-tree from a Json-file specified by *file_path*. 
        """
        f = open(file_path)
        Config = json.load(f)
        f.close()
        
        self.notice_unsaved_changes = False
        self.locos = [self.create_loco(loco_dict,
                                       DictWrapper,
                                       self.unsaved_changes)
                      for loco_dict in Config["locos"]]
        self.server = Server(self.unsaved_changes,
                             *self.get_param_list_from_dict(Config["server"],
                                                            self.server_attributes))
        self.joystick = Joystick(self.unsaved_changes,
                                 *self.get_param_list_from_dict(Config["joystick"],
                                                                self.joystick_attributes))
        # due to a bug in previous 4.x.x-versions,
        # the sound was not saved in the config file -> KeyError
        try:
            self.sound = Sound(self.unsaved_changes,
                               *self.get_param_list_from_dict(Config["sound"],
                                                              self.sound_attributes))
        except KeyError:
            self.sound = Sound(self.unsaved_changes)
        self.active_loco = None
        
        self.has_unsaved_changes = False
        self.save_opened_file(file_path)
        locked_print("Einstellungen wurden geladen aus " + file_path)
        self.notice_unsaved_changes = True
    
    @staticmethod
    def get_param_list_from_dict(config_dict, attribute_list, ignore=False):
        """
        Uses a dictionary *config_dict* and *attribute_list*
        to create a parameter-list which can be fed into a constructor of
        an object.
        *attribute_list* is a list of tuples of the form
        ``[("attribute_name", default_value), ...]``. The default values
        are used, if *config_dict* has no key for the respective
        *attribute_name*. If the *ignore* flag is set to ``false`` (default)
        a warning is printed if a fallback to default values happens.
        
        Example: You could create a new :class:`Server`-object like this::
        
            server_dict = {"host": "localhost",
                           "port": 4303}
            server = Server(self.unsaved_changes,
                            *self.get_param_list_from_dict(server_dict,
                                                           self.server_attributes),
                            True)
            # 'server_dict' doesn't contain all needed keys, so the
            # default-values in self.server_attributes will be used
        """
        param_list = []
        for attrib, standard_value in attribute_list:
            try:
                value = config_dict[attrib]
            except KeyError:
                param_list.append(standard_value)
                if not ignore:
                    locked_print("Dateiformat inkorrekt: Attribut",
                                 attrib,
                                 "ist nicht enthalten, es wurde der Standardwert",
                                 standard_value,
                                 "verwendet.")
            else:
                # convert all unicode-objects into
                # utf-8-bytestrings to avoid ascii-related problems
                param_list.append(JsonModel.get_utf8_bytestring(value))
        return param_list
    
    def save_opened_file(self, file_path):
        """
        Stores the *file_path* of the currently opened
        file in :file:`last_file.json` which will be placed
        in the current working directory.
        """
        if self.last_file != file_path:
            f = open("last_file.json", "w")
            json.dump({"last_file": file_path}, f, indent=2)
            f.close()
            self.last_file = file_path
        self.opened_file = file_path
    
    def create_copy(self):
        """
        Returns a new :class:`JsonModel`-instance, whose object-tree is
        identical, except that it is a recursive copy of the existing one.
        This means, that the new instance and the original one don't share
        any objects, only the tree-structure and the values of the objects
        attributes.
        This allows the :mod:`control_ui` module to modify its own copy of
        the configuration without destroying the original one.
        """
        server = Server(None,
                        *self.get_param_list_from_object(self.server,
                                                         self.server_attributes))
        joystick = Joystick(None,
                            *self.get_param_list_from_object(self.joystick,
                                                             self.joystick_attributes))
        sound = Sound(None,
                      *self.get_param_list_from_object(self.sound,
                                                       self.sound_attributes))
         
        locos = [self.create_loco(loco,
                                  ObjectWrapper,
                                  None)
                 for loco in self.locos]
        return JsonModel(locos, server, joystick, sound)
        
    @staticmethod
    def get_param_list_from_object(obj,
                                   attribute_list,
                                   unused_ignore=False):
        """
        Uses an object *obj* and *attribute_list*
        to create a parameter-list which can be fed into a constructor of
        a new object. Works similar to :func:`get_param_list_from_dict`
        """
        param_list = []
        for attrib, standard_value in attribute_list:
            try:
                param_list.append(getattr(obj, attrib))
            except:
                param_list.append(standard_value)
        return param_list
    
    def unsaved_changes(self, obj, name, value):
        """
        To be called whenever an action changes the JsonModel-object.
        Normally this is done using :class:`UnsavedChangesHandler`.
        """
        if self.notice_unsaved_changes:
            locked_print("Attribute '" + name + "' of object '" +
                         str(obj) + "' has new value:", value)
            self.has_unsaved_changes = True
            # if method has been setup, call it
            if self.opened_file != None \
            and hasattr(self, "new_unsaved_changes_method"):
                self.new_unsaved_changes_method()
