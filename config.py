#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from LockedPrint import locked_print
import json
from Constants import SegmentType

class UnsavedChangesHandler(object):
    def __init__(self, save_status_method):
        self.save_status_method = save_status_method
    
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        self.save_status_method(self, name, value)

class LinearSegmentFunction():
    def load(self, control_points):
        self.control_points = [control_points[0], control_points[-1]]
        self.func_segments = [self.calc_func_segment(self.control_points[0], self.control_points[-1])]
        for point in control_points[:len(control_points) - 1]:
            self.add_control_point(*point)
    
    def add_control_point(self, x, y):
        nr = self.get_segment_nr_from_x(x)
        if nr != None and self.control_points[nr][1] < y < self.control_points[nr + 1][1]:
            self.control_points.insert(nr + 1, (x, y))
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
            if point_left[1] < y:
                self.control_points[nr] = (self.control_points[nr][0], y)
                self.func_segments[nr - 1] = self.calc_func_segment(point_left, self.control_points[nr])
        else:
            point_left = self.control_points[nr - 1]
            point_right = self.control_points[nr + 1]
            if point_left[0] < x < point_right[0] and point_left[1] < y < point_right[1]:
                self.control_points[nr] = (x, y)
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
        seg_nr = self.get_segment_nr_from_x(x)
        if seg_nr != None:
            a, b = self.func_segments[seg_nr]
            y = a * x + b
            return y
    
    def get_x(self, y):
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
                 sound_segments=None,
                 name="Neue Lok",
                 speed_steps=14,
                 max_speed=100.0,
                 address=1,
                 protocol="M 1",
                 accel_duration=4.5,
                 direction=True,
                 img_path="Datei wählen",
                 use_sound=False,
                 start_engine_sound=None,
                 idle_sound=None,
                 quit_engine_sound=None):
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
            self.speed_to_step_func.load([(0.0, 0.0), (100.0, 14.0)])
        else:
            self.speed_to_step_func = speed_to_step_func
        
        self.name = name
        self.address = address
        self.protocol = protocol

        self.accel_duration = accel_duration
        self.direction = direction
        self.img_path = img_path
        self.max_speed = max_speed
        self.speed = 0.0
        self.speed_step = 0.0
        self.last_speed_step = 0
        
        self.use_sound = use_sound
        self.start_engine_sound = start_engine_sound
        self.idle_sound = idle_sound
        self.quit_engine_sound = quit_engine_sound
        self.sound_segments = sound_segments

    def send_to_server(self, bus, socket):
        self.last_speed_step = int(self.speed_step)
        toggled = [False for i in range(max([1] + [function.nr + 1 for function in self.functions]))]
        for function in self.functions:
            if function.state:
                toggled[function.nr] = True
        functions = " ".join(str(int(n)) for n in toggled)
        text = "SET " + str(bus) + " GL " + str(self.address) + " " + str(int(self.direction)) + " " + str(int(self.speed_step)) + " " + str(self.speed_steps) + " " + functions + "\n"
        
        locked_print("\n" + text)
        socket.send(text)
    
    def accelerate(self, value):
        self.speed = min(self.max_speed, max(0, self.speed - value * (0.05 / self.accel_duration * self.max_speed)))
        return self.speed
        
    def toggle_direction(self):
        self.direction = not self.direction
        
class Function(UnsavedChangesHandler):
    def __init__(self, save_status_method, name="", function=0, state=False, button=0, use_push_to_make=False):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.name = name
        self.nr = function
        self.state = state
        self.button = button
        self.use_push_to_make = use_push_to_make
        
    def toggle(self):
        self.state = not self.state
        
class Server(UnsavedChangesHandler):
    def __init__(self, save_status_method, host="localhost", port=4303, loco_bus=1, power=True):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.host = host
        self.port = port
        self.loco_bus = loco_bus
        self.power = power
        
    def toggle_power(self):
        self.power = not self.power
        
class Joystick(UnsavedChangesHandler):
    def __init__(self,
                 save_status_method,
                 emergency_button=0,
                 reverse_button=1,
                 accel_axis=2,
                 focus_button=3,
                 use_auto_focus=True,
                 show_function_nr=False):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.emergency_button = emergency_button
        self.reverse_button = reverse_button
        self.accel_axis = accel_axis
        self.focus_button = focus_button
        self.use_auto_focus = use_auto_focus
        self.show_function_nr = show_function_nr
        
class SoundFunction():
    def __init__(self, segments):
        self.segments = segments
        
    def get_sound(self, x, sound_type):
        segment = self.get_segment_from_x(x)
        if segment != None:
            return getattr(segment, sound_type)
        
    def get_segment_nr_from_x(self, x):
        if x == 0:
            return -1
        else:
            for nr, segment in enumerate(self.segments):
                if segment.start < x <= segment.end:
                    return nr
                    break

class SoundSegment(object):
    private_keys = ["type", "store", "save_status_method"]
    allowed_keys = ["start", "end", "load_sound", "idle_sound", "accel_sound", "decel_sound"] + private_keys
    
    def __init__(self, save_status_method, attrib_dict):
        self.store = {}
        self.save_status_method = save_status_method
        for attrib, value in attrib_dict.items():
            setattr(self, attrib, value)

    def __setattr__(self, key, value): # the great thing about this class: it calculates if it's in the lower, upper position or one in between
        if key in self.allowed_keys:
            object.__setattr__(self, key, value)
            if key not in self.private_keys:
                self.store[key] = value
                self.check_type()
                self.save_status_method(self, key, value)
        else:
            raise LookupError(str(key) + " is not an allowed key for a SoundSegment-Dict")
        
    def __delattr__(self, key):
        object.__delattr__(self, key)
        del self.store[key]
        self.check_type()
        
    def check_type(self):
        keys = self.store.keys()
        #print keys
        if "decel_sound" in keys:
            if "accel_sound" in keys:
                self.type = SegmentType.MIDDLE
            else:
                self.type = SegmentType.UPPER
            
            
    def to_dict(self):
        return self.store
            

class Config():
    notice_unsaved_changes = False
    has_unsaved_changes = False
    opened_file = None
    
    loco_attributes = [("name", "Neue Lok"),
                       ("speed_steps", 14),
                       ("max_speed", 100.0),
                       ("address", 1),
                       ("protocol", "M 1"),
                       ("accel_duration", 4.5),
                       ("direction", True),
                       ("img_path", None),
                       ("use_sound", False),
                       ("start_engine_sound", None),
                       ("idle_sound", None),
                       ("quit_engine_sound", None)]
    
    function_attributes = [("name", ""),
                           ("nr", 0),
                           ("state", False),
                           ("button", 0),
                           ("use_push_to_make", False)]
    
    server_attributes = [("host", "localhost"),
                         ("port", 4303),
                         ("loco_bus", 1),
                         ("power", True)]
    
    joystick_attributes = [("emergency_button", 0),
                           ("reverse_button", 1),
                           ("accel_axis", 2),
                           ("focus_button", 3),
                           ("use_auto_focus", True),
                           ("show_function_nr", False)]
    
    def __init__(self):
        self.locos = []
        self.server = Server(self.unsaved_changes)
        self.joystick = Joystick(self.unsaved_changes)
        try:
            f = open("last_file.json")
            self.last_file = json.load(f)["last_file"]
            f.close()
        except IOError:
            self.last_file = ""
            locked_print("Noch kein letzter Dateipfad gespeichert.")
        
    def save(self, file_path):
        loco_list = []
        for loco in self.locos:
            loco_dict = self.get_param_dict(loco, self.loco_attributes)
            loco_dict["speed_control_points"] = loco.speed_to_step_func.control_points
            if loco.sound_segments != None:
                loco_dict["sound_segments"] = [segment.to_dict() for segment in loco.sound_segments]
            else:
                loco_dict["sound_segments"] = None
            function_list = [self.get_param_dict(function, self.function_attributes)
                             for function in loco.functions]
            loco_dict["functions"] = function_list
            loco_list.append(loco_dict)
            
        server_dict = self.get_param_dict(self.server, self.server_attributes)
        joystick_dict = self.get_param_dict(self.joystick, self.joystick_attributes)
        Config = {"locos": loco_list, "server": server_dict, "joystick": joystick_dict}
            
        f = open(file_path, "w")
        json.dump(Config, f, indent=2)
        f.close()
            
        self.has_unsaved_changes = False
        self.save_opened_file(file_path)
        locked_print("Einstellungen wurden gespeichert in " + file_path)
        
    def get_param_dict(self, config_object, attribute_list):
        return {attrib[0]: getattr(config_object, attrib[0]) for attrib in attribute_list}
        
    def load(self, file_path):
        f = open(file_path)
        Config = json.load(f)
        f.close()
        
        self.notice_unsaved_changes = False
        self.locos = []
        for loco_dict in Config["locos"]:
            functions = [Function(self.unsaved_changes,
                                  *self.get_param_list(function_dict, self.function_attributes))
                         for function_dict in loco_dict["functions"]]
            speed_func = LinearSegmentFunction()
            speed_func.load(loco_dict["speed_control_points"])
            if loco_dict["sound_segments"] != None:
                try:
                    sound_segments = [SoundSegment(self.unsaved_changes, segment_dict) for segment_dict in loco_dict["sound_segments"]]
                except KeyError:
                    locked_print("Die Datei besitzt noch keine Geräusch-Informationen.")
                    sound_segments = None
            else:
                sound_segments = None
            
            self.locos.append(Loco(self.unsaved_changes,
                                   functions,
                                   speed_func,
                                   sound_segments,
                                   *self.get_param_list(loco_dict, self.loco_attributes)))
        self.server = Server(self.unsaved_changes,
                             *self.get_param_list(Config["server"], self.server_attributes))
        self.joystick = Joystick(self.unsaved_changes,
                                 *self.get_param_list(Config["joystick"], self.joystick_attributes))
        
        self.has_unsaved_changes = False
        self.save_opened_file(file_path)
        locked_print("Einstellungen wurden geladen aus " + file_path)
        self.notice_unsaved_changes = True
    
    def get_param_list(self, config_dict, attribute_list):
        param_list = []
        for attrib, standard_value in attribute_list:
            try:
                value = config_dict[attrib]
                if isinstance(value, unicode): # convert all unicode-objects into utf-8-bytestrings to avoid ascii-related problems
                    value = value.encode("utf-8")
                param_list.append(value)
            except KeyError:
                param_list.append(standard_value)
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

    def unsaved_changes(self, obj, name, value):
        if self.notice_unsaved_changes:
            locked_print("Attribute '" + name + "' of object '" + str(obj) + "' has new value:", value)
            self.has_unsaved_changes = True
            if self.opened_file != None and hasattr(self, "new_unsaved_changes_method"): # if method has been setup, call it
                self.new_unsaved_changes_method()
