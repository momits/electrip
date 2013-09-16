#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from LockedPrint import locked_print
import json
from Constants import SegmentPosition, EngineType, ToggleMode
from os.path import basename, split, exists, sep as os_sep
import zipfile

class UnsavedChangesHandler(object):
    def __init__(self, save_status_method):
        if save_status_method != None:
            self.save_status_method = save_status_method
    
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if hasattr(self, "save_status_method"):
            self.save_status_method(self, name, value)

class LinearSegmentFunction:
#    def __init__(self):
#        self.type = type
        
    def load(self, control_points):
        self.control_points = [control_points[0], control_points[-1]]
        self.func_segments = [self.calc_func_segment(self.control_points[0], self.control_points[-1])]
        for point in control_points[1:len(control_points) - 1]:
            self.add_control_point(*point)
    
    def add_control_point(self, x, y):
        nr = self.get_segment_nr_from_x(x)
        if nr != None:
#            if self.type == FunctionType.MONOTONIC_INCREASE:
            self.control_points.insert(nr + 1, (x, max(self.control_points[nr][1] , min(y, self.control_points[nr + 1][1]))))
#            elif self.type == FunctionType.MONOTONIC_DECREASE:
#                self.control_points.insert(nr + 1, (x, min(self.control_points[nr][1] , max(y, self.control_points[nr + 1][1]))))
            self.func_segments[nr] = self.calc_func_segment(self.control_points[nr], self.control_points[nr + 1])
            self.func_segments.insert(nr + 1, self.calc_func_segment(self.control_points[nr + 1], self.control_points[nr + 2]))
                
    def remove_control_point(self, nr):
        if nr != 0 and nr != len(self.control_points) - 1:
            self.control_points.pop(nr)
            del self.func_segments[nr - 1: nr + 1]
            self.func_segments.insert(nr - 1, self.calc_func_segment(self.control_points[nr - 1], self.control_points[nr]))
        
    def move_control_point(self, nr, x, y):
        if nr == len(self.control_points) - 1:
            point_left = self.control_points[nr - 1]
#            if self.type == FunctionType.MONOTONIC_INCREASE:
            self.control_points[nr] = (self.control_points[nr][0], max(y, point_left[1]))
#            elif self.type == FunctionType.MONOTONIC_DECREASE:
#                self.control_points[nr] = (self.control_points[nr][0], min(y, point_left[1]))
            self.func_segments[nr - 1] = self.calc_func_segment(point_left, self.control_points[nr])
        elif nr == 0:
            point_right = self.control_points[nr + 1]
#            if self.type == FunctionType.MONOTONIC_INCREASE:
            self.control_points[nr] = (self.control_points[nr][0], min(y, point_right[1]))
#            elif self.type == FunctionType.MONOTONIC_DECREASE:
#                self.control_points[nr] = (self.control_points[nr][0], min(y, point_left[1]))
            self.func_segments[nr] = self.calc_func_segment(self.control_points[nr], point_right)
            
        else:
            point_left = self.control_points[nr - 1]
            point_right = self.control_points[nr + 1]
            if point_left[0] < x < point_right[0]:
#                if self.type == FunctionType.MONOTONIC_INCREASE:
                self.control_points[nr] = (x, min(point_right[1], max(y, point_left[1])))
#                elif self.type == FunctionType.MONOTONIC_DECREASE:
#                    self.control_points[nr] = (x, min(point_left[1], max(y, point_right[1])))
                self.func_segments[nr] = self.calc_func_segment(self.control_points[nr], point_right)
                self.func_segments[nr - 1] = self.calc_func_segment(point_left, self.control_points[nr])
        return self.control_points[nr]
                        
    def calc_func_segment(self, point1, point2):
        x1, y1 = point1
        x2, y2 = point2
        a = (y2 - y1) / (x2 - x1)
        b = y2 - x2 * a
        return a, b
            
    def get_y(self, x):
        if x == 0:
            return 0
        else:
            seg_nr = self.get_segment_nr_from_x(x)
            if seg_nr != None:
                a, b = self.func_segments[seg_nr]
                y = a * x + b
                return y
    
    def get_x(self, y):
        if y == 0:
            return 0
        else:
            seg_nr = self.get_segment_nr_from_y(y)
            if seg_nr != None:
                a, b = self.func_segments[seg_nr]
                x = (y - b) / a
                if x > self.control_points[seg_nr][0]:
                    return x
    
    def get_segment_nr_from_x(self, x):
        for nr in xrange(len(self.control_points) - 1):
            if self.control_points[nr][0] <= x <= self.control_points[nr + 1][0]:
                return nr
                break
            
    def get_segment_nr_from_y(self, y):
        for nr in xrange(len(self.control_points) - 1):
            if self.control_points[nr][1] <= y <= self.control_points[nr + 1][1]:
                return nr
                break

class Loco(UnsavedChangesHandler):
    def __init__(self,
                 save_status_method,
                 functions=None,
                 speed_to_step_func=None,
                 function_sounds=None,
                 engine=None,
                 name="Unbenannte Lok",
                 speed_steps=128,
                 max_speed=100.0,
                 address=1,
                 protocol="N 1",
                 accel_duration=11.5,
                 decel_duration=8.5,
                 direction=True,
                 img_path=None,
                 sound_volume=0.8,):
        UnsavedChangesHandler.__init__(self, save_status_method)
        # it is not possible to set the default value for the "functions"-parameter above,
        # because it is a list and will therefore be the same object for all locos, resulting in the same functions for all locos
        if functions == None:
            self.functions = []
        else:
            self.functions = functions
        self.speed_steps = speed_steps
        if speed_to_step_func == None:
            self.speed_to_step_func = LinearSegmentFunction()
            self.speed_to_step_func.load([(0.0, 0.0), (100.0, 128.0)])
        else:
            self.speed_to_step_func = speed_to_step_func
        if function_sounds == None:
            self.function_sounds = []
        else:
            self.function_sounds = function_sounds
        self.name = name
        self.address = address
        self.protocol = protocol

        self.accel_duration = accel_duration
        self.decel_duration = decel_duration
        self.direction = direction
        self.img_path = img_path
        self.max_speed = max_speed
        self.speed = 0.0
        self.speed_step = 0.0
        self.last_speed_step = 0
        
        self.sound_volume = sound_volume
        self.engine = engine

    def get_srcp_status(self, bus):
        self.last_speed_step = int(self.speed_step)
        if len(self.functions) > 0:
            toggled = [False for i in range(max([function.nr + 1 for function in self.functions]))]
            for function in self.functions:
                if function.state:
                    toggled[function.nr] = True
            functions = " " + " ".join(str(int(val)) for val in toggled)
        else:
            functions = ""
        text = "SET " + str(bus) + " GL " + str(self.address) + " " \
                + str(int(self.direction)) + " " + str(int(self.speed_step)) \
                + " " + str(self.speed_steps) + functions + "\n"
        
        locked_print(text)
        return text
    
    def accelerate(self, value): # value between -1 and 1, -1 means acceleration
        if value < 0:
            self.speed = min(self.max_speed, max(0, self.speed - value * (0.05 / self.accel_duration * self.max_speed)))
        else:
            self.speed = min(self.max_speed, max(0, self.speed - value * (0.05 / self.decel_duration * self.max_speed)))
        return self.speed
        
    def toggle_direction(self):
        self.direction = not self.direction
        
class GamepadFunction(UnsavedChangesHandler):
    def __init__(self, save_status_method, name="", state=False, button=0):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.name = name
        self.state = state
        self.button = button
        
    def toggle(self):
        self.state = not self.state
        
class Function(GamepadFunction):
    def __init__(self, save_status_method, name="", function=0, state=False, button=0, toggle_mode=ToggleMode.SWITCH):
        GamepadFunction.__init__(self,
                                 save_status_method,
                                 name,
                                 state,
                                 button)
        self.nr = function
        self.toggle_mode = toggle_mode
        
class Server(UnsavedChangesHandler):
    def __init__(self, save_status_method, host="localhost", port=4303, bus=1, power=True):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.host = host
        self.port = port
        self.bus = bus
        self.power = power
        
    def toggle_power(self):
        self.power = not self.power
        
class Joystick(UnsavedChangesHandler):
    def __init__(self,
                 save_status_method,
                 emergency_button=0,
                 reverse_button=1,
                 accel_axis=2,
                 axis_threshold=0.06,
                 focus_button=3,
                 sound_button=4,
                 use_auto_focus=True,
                 show_function_nr=False):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.emergency_button = emergency_button
        self.reverse_button = reverse_button
        self.accel_axis = accel_axis
        self.axis_threshold = axis_threshold
        self.focus_button = focus_button
        self.sound_button = sound_button
        self.use_auto_focus = use_auto_focus
        self.show_function_nr = show_function_nr
        
class Sound(UnsavedChangesHandler):
    def __init__(self,
                 save_status_method,
                 sampling_rate=44100,
                 show_level_bar=True):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.sampling_rate = sampling_rate
        self.show_level_bar = show_level_bar
        
class EventSound(GamepadFunction):
    def __init__(self,
                 save_status_method,
                 name="",
                 file_path=None,
                 state=True,
                 min_speed=None,
                 max_speed=None,
                 min_accel=None,
                 max_accel=None,
                 button=0):
        GamepadFunction.__init__(self,
                                 save_status_method,
                                 name,
                                 state,
                                 button)
        self.file_path = file_path
        self.min_speed = min_speed
        self.max_speed = max_speed
        self.min_accel = min_accel
        self.max_accel = max_accel
        
class FunctionSound(GamepadFunction):
    def __init__(self,
                 save_status_method,
                 name="",
                 file_path=None,
                 state=False,
                 button=0,
                 toggle_mode=ToggleMode.TAP):
        GamepadFunction.__init__(self,
                                 save_status_method,
                                 name,
                                 state,
                                 button)
        self.file_path = file_path
        self.toggle_mode = toggle_mode

class SoundFunction:
    def __init__(self, segments):
        self.segments = segments
        
    def get_sound(self, x, sound_type):
        nr = self.get_segment_nr_from_x(x)
        if nr != None:
            return getattr(self.segments[nr], sound_type)
        
    def get_segment_nr_from_x(self, x):
        if x == 0:
            return -1
        else:
            for nr, segment in enumerate(self.segments):
                if segment.start < x <= segment.end:
                    return nr
                    break

def create_sound_segment(engine_type, *args):
    if engine_type == EngineType.STEAM:
        return SteamSoundSegment(*args)
    elif engine_type == EngineType.DIESEL:
        return DieselSoundSegment(*args)

class SoundSegment(UnsavedChangesHandler):
    position = SegmentPosition.MIDDLE
    def __init__(self, save_status_method, start, end):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.start = start
        self.end = end
    
class DieselSoundSegment(SoundSegment):
    type = "diesel"
    attributes = {SegmentPosition.UPPER: ["start", "end", "load_sound", "accel_sound", "decel_sound"],
                  SegmentPosition.MIDDLE: ["start", "end", "load_sound", "idle_sound", "accel_sound", "decel_sound"]}
    position = SegmentPosition.MIDDLE
    def __init__(self,
                 save_status_method,
                 start,
                 end,
                 load_sound=None,
                 idle_sound=None,
                 accel_sound=None,
                 decel_sound=None):
        SoundSegment.__init__(self, save_status_method, start, end)
        self.load_sound = load_sound
        self.idle_sound = idle_sound
        self.accel_sound = accel_sound
        self.decel_sound = decel_sound
                
    def set_position(self, position):
        if position != self.position:
            if position == SegmentPosition.MIDDLE:
                self.idle_sound = None
                self.position = SegmentPosition.MIDDLE
            elif position == SegmentPosition.UPPER:
                del self.idle_sound
                self.position = SegmentPosition.UPPER

class SteamSoundSegment(SoundSegment):
    type = "steam"
    def __init__(self,
                 save_status_method,
                 start,
                 end,
                 stroke_sounds=None):
        SoundSegment.__init__(self, save_status_method, start, end)
        self.stroke_sounds = stroke_sounds
        
    def set_position(self, position):
        pass # no need to do anything (position just doesnt matter)

def create_engine(engine_type, *args):
    if engine_type == EngineType.DIESEL:
        return DieselEngine(*args)
    elif engine_type == EngineType.STEAM:
        return SteamEngine(*args)

class Engine(UnsavedChangesHandler):
    def __init__(self, save_status_method, sound_segments, event_sounds):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.sound_segments = sound_segments
        if self.sound_segments != None:
            self.sound_function = SoundFunction(self.sound_segments)
        else:
            self.sound_function = None
        if event_sounds == None:
            self.event_sounds = []
        else:
            self.event_sounds = event_sounds

class DieselEngine(Engine):
    type = "diesel"
    def __init__(self,
                 save_status_method,
                 start_sound=None,
                 idle_sound=None,
                 quit_sound=None,
                 sound_segments=None,
                 event_sounds=None):
        Engine.__init__(self, save_status_method, sound_segments, event_sounds)
        self.start_sound = start_sound
        self.idle_sound = idle_sound
        self.quit_sound = quit_sound
        
class SteamEngine(Engine):
    type = "steam"
    def __init__(self,
                 save_status_method,
                 idle_sound=None,
                 cylinder_steam_sound=None,
                 nr_strokes=4,
                 stroke_start_delay=2.0,
                 wheel_diameter=1.2,
                 min_freq=0.2,
                 sound_segments=None,
                 event_sounds=None):
        Engine.__init__(self, save_status_method, sound_segments, event_sounds)
        self.idle_sound = idle_sound
        self.cylinder_steam_sound = cylinder_steam_sound
        self.nr_strokes = nr_strokes
        self.stroke_start_delay = stroke_start_delay
        self.wheel_diameter = wheel_diameter
        self.min_freq = min_freq
        self.sound_segments = sound_segments

class DictWrapper:
    @staticmethod
    def get(d, k):
        return d[k]
    
    @staticmethod
    def has_key(d, k):
        return k in d
    
    @staticmethod
    def set(d, k, v):
        d[k] = v
        
class ObjectWrapper:
    @staticmethod
    def get(o, a):
        return getattr(o, a)
    
    @staticmethod
    def has_key(o, a):
        return hasattr(o, a)
    
    @staticmethod
    def set(o, a, v):
        setattr(o, a, v)

class Config:
    notice_unsaved_changes = False
    has_unsaved_changes = False
    opened_file = None
    
    loco_attributes = [("name", "Unbenannte Lok"),
                       ("speed_steps", 128),
                       ("max_speed", 100.0),
                       ("address", 1),
                       ("protocol", "N 1"),
                       ("accel_duration", 11.5),
                       ("decel_duration", 8.5),
                       ("direction", True),
                       ("img_path", None),
                       ("sound_volume", 0)]
    
    engine_attributes = {"diesel":
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
    
    event_sound_attributes = [("name", ""),
                              ("file_path", None),
                              ("state", True),
                              ("min_speed", None),
                              ("max_speed", None),
                              ("min_accel", None),
                              ("max_accel", None),
                              ("button", 0)]
    
    function_sound_attributes = [("name", ""),
                                 ("file_path", None),
                                 ("state", False),
                                 ("button", 0),
                                 ("toggle_mode", ToggleMode.TAP)]
    
    segment_attributes = {"diesel":
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
    
    function_attributes = [("name", ""),
                           ("nr", 0),
                           ("state", False),
                           ("button", 0),
                           ("toggle_mode", ToggleMode.SWITCH)]
    
    server_attributes = [("host", "localhost"),
                         ("port", 4303),
                         ("bus", 1),
                         ("power", True)]
    
    joystick_attributes = [("emergency_button", 0),
                           ("reverse_button", 1),
                           ("accel_axis", 2),
                           ("axis_threshold", 0.06),
                           ("focus_button", 3),
                           ("sound_button", 4),
                           ("use_auto_focus", True),
                           ("show_function_nr", False)]
    
    sound_attributes = [("sampling_rate", 44100),
                        ("show_level_bar", True)]
    
    def __init__(self, locos=None, server=None, joystick=None, sound=None):
        if locos == None:
            self.locos = []
        else:
            self.locos = locos
        if server == None:
            self.server = Server(self.unsaved_changes)
        else:
            self.server = server
        if joystick == None:
            self.joystick = Joystick(self.unsaved_changes)
        else:
            self.joystick = joystick
        if sound == None:
            self.sound = Sound(self.unsaved_changes)
        else:
            self.sound = sound
        self.active_loco = None # loco that is currently configured
        
        try:
            f = open("last_file.json")
            self.last_file = json.load(f)["last_file"]
            f.close()
        except IOError:
            self.last_file = ""
            locked_print("Noch kein letzter Dateipfad gespeichert.")
            
    def get_utf8_bytestring(self, value):
        if isinstance(value, unicode):
            value = value.encode("utf-8")
        return value
            
    def add_file_to_zip(self, zip_file, file_path, dest=""):
        try:
            file_name = basename(file_path)
            if dest != "":
                file_name = dest + os_sep + file_name
            zip_file.write(file_path, file_name)
        except (OSError, AttributeError): # attrib-error occurs if file_path is None
            locked_print("Ungültige Datei '" + str(file_path) + "' konnte nicht in Lok-Verzeichnis kopiert werden.")
            return None
        else:
            return file_name
        
    def add_files_to_zip(self, zip_file, config_object, attribs, dest=""):
        for attrib in attribs:
            if hasattr(config_object, attrib):
                file_path = getattr(config_object, attrib)
                file_name = self.add_file_to_zip(zip_file, file_path, dest)
                setattr(config_object, attrib, file_name)
        
    def save_loco(self, loco, dir_path):
        file_path = dir_path + os_sep + loco.name + ".zip"
        with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED, True) as zip_file:
            save_status_method = self.new_unsaved_changes_method
            del self.new_unsaved_changes_method # remove any references to GObjects, as they are not copyable
            self.notice_unsaved_changes = False
            loco = self.create_loco(loco,
                                    ObjectWrapper,
                                    self.get_param_list_from_object,
                                    None) # we dont want to mess our existing config, but create a new object instead
            if loco.engine != None:
                if loco.engine.type == EngineType.STEAM:
                    for segment in loco.engine.sound_segments:
                        segment.stroke_sounds = [self.add_file_to_zip(zip_file, stroke_sound, "sound") for stroke_sound in segment.stroke_sounds]
                    self.add_files_to_zip(zip_file, loco.engine, ["idle_sound", "cylinder_steam_sound"], "sound")
                    
                elif loco.engine.type == EngineType.DIESEL:
                    for segment in loco.engine.sound_segments:
                        self.add_files_to_zip(zip_file, segment, ["load_sound", "idle_sound", "accel_sound", "decel_sound"], "sound")
                    self.add_files_to_zip(zip_file, loco.engine, ["start_sound", "idle_sound", "quit_sound"], "sound")
                    
                for sound in loco.engine.event_sounds:
                    sound.file_path = self.add_file_to_zip(zip_file, sound.file_path, "sound")
                        
            for sound in loco.function_sounds:
                sound.file_path = self.add_file_to_zip(zip_file, sound.file_path, "sound")
                    
            loco.img_path = self.add_file_to_zip(zip_file, loco.img_path, "image")
            zip_file.writestr(loco.name + ".loco", json.dumps(self.create_loco_dict(loco), indent=2)) # write config file
            locked_print("Lok wurde gespeichert in", file_path)
            self.new_unsaved_changes_method = save_status_method # restore ref to GObject
            self.notice_unsaved_changes = True
        
    def create_loco_dict(self, loco):
        loco_dict = self.get_param_dict(loco, self.loco_attributes)
        loco_dict["speed_control_points"] = loco.speed_to_step_func.control_points
        loco_dict["function_sounds"] = [self.get_param_dict(function_sound, self.function_sound_attributes)
                                        for function_sound in loco.function_sounds]
        if loco.engine != None:
            engine_dict = self.get_param_dict(loco.engine, self.engine_attributes[loco.engine.type])
            if loco.engine.sound_segments != None:
                engine_dict["sound_segments"] = [self.get_param_dict(segment, self.segment_attributes[segment.type])
                                                 for segment in loco.engine.sound_segments]
            else:
                engine_dict["sound_segments"] = None
            if loco.engine.event_sounds != None:
                engine_dict["event_sounds"] = [self.get_param_dict(event_sound, self.event_sound_attributes)
                                                 for event_sound in loco.engine.event_sounds]
            else:
                engine_dict["event_sounds"] = None
            loco_dict["engine"] = engine_dict
        else:
            loco_dict["engine"] = None
        function_list = [self.get_param_dict(function, self.function_attributes)
                         for function in loco.functions]
        loco_dict["functions"] = function_list
        return loco_dict
        
    def save(self, file_path):
        Config = {"locos": [self.create_loco_dict(loco) for loco in self.locos],
                  "server": self.get_param_dict(self.server, self.server_attributes),
                  "joystick": self.get_param_dict(self.joystick, self.joystick_attributes),
                  "sound": self.get_param_dict(self.sound, self.sound_attributes)}
        
        f = open(file_path, "w")
        json.dump(Config, f, indent=2)
        f.close()
            
        self.has_unsaved_changes = False
        self.save_opened_file(file_path)
        locked_print("Einstellungen wurden gespeichert in " + file_path)
        
    def get_param_dict(self, config_object, attribute_list):
        param_dict = {}
        for attrib in attribute_list:
            try:
                param_dict[attrib[0]] = getattr(config_object, attrib[0])
            except AttributeError:
                pass # needed for objects where we don't know if they have a certain attribute (e.g. sound_segments)
        return param_dict
    
    def set_absolute_path(self, path_prefix, config_object, attribs): # appends path_prefix to all attribs of config_object
        for attrib in attribs:
            file_name = getattr(config_object, attrib)
            if file_name != None and exists(path_prefix + file_name):
                setattr(config_object, attrib, path_prefix + file_name)
            else:
                setattr(config_object, attrib, file_name)
    
    def load_loco(self, file_path):
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
                                    self.get_param_list_from_dict,
                                    self.unsaved_changes)
            if loco.engine != None:
                if loco.engine.type == EngineType.STEAM:
                    for segment in loco.engine.sound_segments:
                        segment.stroke_sounds = [dir_path + stroke_sound for stroke_sound in segment.stroke_sounds if stroke_sound != None]
                    self.set_absolute_path(dir_path, loco.engine, ["idle_sound", "cylinder_steam_sound"])
                    
                elif loco.engine.type == EngineType.DIESEL:
                    for segment in loco.engine.sound_segments:
                        self.set_absolute_path(dir_path, segment, ["load_sound", "idle_sound", "accel_sound", "decel_sound"])
                    self.set_absolute_path(dir_path, loco.engine, ["start_sound", "idle_sound", "quit_sound"])
                    
                for sound in loco.engine.event_sounds:
                    self.set_absolute_path(dir_path, sound, ["file_path"])
                    
            for sound in loco.function_sounds:
                self.set_absolute_path(dir_path, sound, ["file_path"])
                
            self.set_absolute_path(dir_path, loco, ["img_path"])
            return loco

    def create_loco(self, loco_obj, wrapper, get_param_list, unsaved_changes_method):
        functions = []
        for function_obj in wrapper.get(loco_obj, "functions"):
            if not wrapper.has_key(function_obj, "toggle_mode"): # old file format has no attrib 'toggle_mode', but bool 'use_push_to_make'
                if wrapper.get(function_obj, "use_push_to_make"):
                    wrapper.set(function_obj, "toggle_mode", ToggleMode.PUSH)
                else:
                    wrapper.set(function_obj, "toggle_mode", ToggleMode.SWITCH)
            functions.append(Function(unsaved_changes_method,
                                      *get_param_list(function_obj, self.function_attributes)))
        speed_func = LinearSegmentFunction()
        if wrapper == DictWrapper:
            speed_func.load(map(tuple, wrapper.get(loco_obj, "speed_control_points")))
        else:
            speed_func.load(wrapper.get(wrapper.get(loco_obj, "speed_to_step_func"), "control_points"))
        if wrapper.has_key(loco_obj, "function_sounds"):
            function_sounds = [FunctionSound(unsaved_changes_method,
                                             *get_param_list(function_sound_obj, self.function_sound_attributes))
                               for function_sound_obj in wrapper.get(loco_obj, "function_sounds")]
        else:
            function_sounds = None
        if  wrapper.has_key(loco_obj, "engine") and wrapper.get(loco_obj, "engine") != None:
            engine_obj = wrapper.get(loco_obj, "engine")
            param_list = get_param_list(engine_obj, self.engine_attributes[wrapper.get(engine_obj, "type")])
            param_list.insert(1, unsaved_changes_method)
            if wrapper.get(engine_obj, "sound_segments") != None:
                try:
                    sound_segments = [create_sound_segment(wrapper.get(engine_obj, "type"),
                                                           unsaved_changes_method,
                                                           *get_param_list(segment_obj,
                                                                           self.segment_attributes[wrapper.get(engine_obj, "type")],
                                                                           True))
                                      for segment_obj in wrapper.get(engine_obj, "sound_segments")]
                except KeyError:
                    locked_print("Die Datei besitzt noch keine Geräusch-Informationen.")
                    sound_segments = None
            else:
                sound_segments = None
            param_list.append(sound_segments)
            if wrapper.has_key(engine_obj, "event_sounds"):
                if wrapper.get(engine_obj, "event_sounds") != None:
                    param_list.append([EventSound(unsaved_changes_method,
                                                  *get_param_list(event_sound_obj, self.event_sound_attributes))
                                       for event_sound_obj in wrapper.get(engine_obj, "event_sounds")])
            engine = create_engine(*param_list)
        else:
            engine = None
             
        return Loco(unsaved_changes_method,
                    functions,
                    speed_func,
                    function_sounds,
                    engine,
                    *get_param_list(loco_obj, self.loco_attributes))

    def load(self, file_path):
        f = open(file_path)
        Config = json.load(f)
        f.close()
        
        self.notice_unsaved_changes = False
        self.locos = [self.create_loco(loco_dict,
                                       DictWrapper,
                                       self.get_param_list_from_dict,
                                       self.unsaved_changes)
                      for loco_dict in Config["locos"]]
        self.server = Server(self.unsaved_changes,
                             *self.get_param_list_from_dict(Config["server"], self.server_attributes))
        self.joystick = Joystick(self.unsaved_changes,
                                 *self.get_param_list_from_dict(Config["joystick"], self.joystick_attributes))
        try: # due to a bug in previous 4.x.x-versions, the sound was not saved in the config file -> KeyError
            self.sound = Sound(self.unsaved_changes,
                               *self.get_param_list_from_dict(Config["sound"], self.sound_attributes))
        except KeyError:
            self.sound = Sound(self.unsaved_changes)
        self.active_loco = None
        
        self.has_unsaved_changes = False
        self.save_opened_file(file_path)
        locked_print("Einstellungen wurden geladen aus " + file_path)
        self.notice_unsaved_changes = True
    
    def get_param_list_from_dict(self, config_dict, attribute_list, ignore=False):
        param_list = []
        for attrib, standard_value in attribute_list:
            try:
                value = self.get_utf8_bytestring(config_dict[attrib]) # convert all unicode-objects into utf-8-bytestrings to avoid ascii-related problems
                param_list.append(value)
            except KeyError:
                param_list.append(standard_value)
                if not ignore:
                    locked_print("Dateiformat inkorrekt: Attribut",
                                 attrib,
                                 "ist nicht enthalten, es wurde der Standardwert",
                                 standard_value,
                                 "verwendet.")
        return param_list
    
    def save_opened_file(self, file_path):
        if self.last_file != file_path:
            f = open("last_file.json", "w")
            json.dump({"last_file": file_path}, f, indent=2)
            f.close()
            self.last_file = file_path
        self.opened_file = file_path
    
    def create_copy(self):
        server = Server(None, *self.get_param_list_from_object(self.server, self.server_attributes))
        joystick = Joystick(None, *self.get_param_list_from_object(self.joystick, self.joystick_attributes))
        sound = Sound(None, *self.get_param_list_from_object(self.sound, self.sound_attributes))
         
        locos = [self.create_loco(loco,
                                  ObjectWrapper,
                                  self.get_param_list_from_object,
                                  None)
                 for loco in self.locos]
        return Config(locos, server, joystick, sound)
        
    def get_param_list_from_object(self, obj, attribs, unused_ignore=False):
        param_list = []
        for attrib, standard_value in attribs:
            try:
                param_list.append(getattr(obj, attrib))
            except:
                pass
        return param_list
    
    def unsaved_changes(self, obj, name, value):
        if self.notice_unsaved_changes:
            locked_print("Attribute '" + name + "' of object '" + str(obj) + "' has new value:", value)
            self.has_unsaved_changes = True
            if self.opened_file != None and hasattr(self, "new_unsaved_changes_method"): # if method has been setup, call it
                self.new_unsaved_changes_method()
