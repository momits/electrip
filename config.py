#!/usr/bin/env python
# -*- coding: UTF 8 -*-

from LockedPrint import locked_print
import json

class UnsavedChangesHandler(object):
    def __init__(self, save_status_method):
        self.save_status_method = save_status_method
    
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        self.save_status_method(self, name, value)

class LinearSegmentFunction():
    def load(self, control_points):
        self.control_points = [control_points[0], control_points[-1]] #control_points[1], 
        self.func_segments = [self.calc_func_segment(self.control_points[0], self.control_points[-1])] #self.control_points[0], self.control_points[1]), 
        for point in control_points[:len(control_points) - 1]:
            self.add_control_point(*point)
    
    def add_control_point(self, x, y):
        nr = self.get_segment_nr_from_x(x)
        if nr != None and self.control_points[nr][1] < y < self.control_points[nr + 1][1]: #and nr != 0 
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
                 save_status_method, #id
                 functions=None,
                 speed_to_step_func=None,
                 name="Neue Lok",
                 speed_steps=14,
                 max_speed=100.0,
                 address=1,
                 protocol="M 1",
                 accel_duration=3.8,
                 direction=True,
                 img_path="Datei wählen"):
        UnsavedChangesHandler.__init__(self, save_status_method)
#        self.id = id
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

    def send_to_server(self, bus, socket):
        self.last_speed_step = int(self.speed_step)
        toggled = [False for i in range(max([0] + [function.nr for function in self.functions]))]
        for function in self.functions:
            if function.state:
                toggled[function.nr - 1] = True
        functions = " ".join(str(int(n)) for n in toggled)
        text = "SET " + str(bus) + " GL " + str(self.address) + " " + str(int(self.direction)) + " " + str(int(self.speed_step)) + " " + str(self.speed_steps) + " " + functions + "\n"
        
        locked_print("\n" + text)
        socket.send(text)
    
    def accelerate(self, value, controller):
        self.speed = self.speed - value * (0.05 / self.accel_duration * self.max_speed)
        controller.speed_scale.set_value(self.speed)
        
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
    def __init__(self, save_status_method, host="localhost", port=4303, session_bus=0, loco_bus=1, power=True):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.host = host
        self.port = port
        self.session_bus = session_bus
        self.loco_bus = loco_bus
        self.power = power
        
    def toggle_power(self):
        self.power = not self.power
        
class Joystick(UnsavedChangesHandler):
    def __init__(self, save_status_method, emergency_button=0, reverse_button=1, accel_axis=2, focus_button=3, use_auto_focus=True, show_function_nr=False):
        UnsavedChangesHandler.__init__(self, save_status_method)
        self.emergency_button = emergency_button
        self.reverse_button = reverse_button
        self.accel_axis = accel_axis
        self.focus_button = focus_button
        self.use_auto_focus = use_auto_focus
        self.show_function_nr = show_function_nr
    
class Config():
    notice_unsaved_changes = False
    has_unsaved_changes = False
    opened_file = None
    
    loco_attributes = ["name", "speed_steps", "max_speed", "address", "protocol", "accel_duration", "direction", "img_path"] #, "speed_to_step_func.control_points"
    function_attributes = ["name", "nr", "state", "button", "use_push_to_make"]
    server_attributes = ["host", "port", "session_bus", "loco_bus", "power"]
    joystick_attributes = ["emergency_button", "reverse_button", "accel_axis", "focus_button", "use_auto_focus", "show_function_nr"]
    
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
            loco_dict = {attrib: getattr(loco, attrib) for attrib in self.loco_attributes}
            loco_dict["speed_control_points"] = loco.speed_to_step_func.control_points
            function_list = [{attrib: getattr(function, attrib) for attrib in self.function_attributes} for function in loco.functions]
            loco_dict["functions"] = function_list
            loco_list.append(loco_dict)
            server_dict = {attrib: getattr(self.server, attrib) for attrib in self.server_attributes}
            joystick_dict = {attrib: getattr(self.joystick, attrib) for attrib in self.joystick_attributes}
            Config = {"locos": loco_list, "server": server_dict, "joystick": joystick_dict}
            
            f = open(file_path, "w")
            json.dump(Config, f, indent=2)
            f.close()
            
        self.has_unsaved_changes = False
        self.save_opened_file(file_path)
        locked_print("Einstellungen wurden gespeichert in " + file_path)
        
    def load(self, file_path): #TODO: allow loading older files which don't have all the attribs of the new format
        f = open(file_path)
        Config = json.load(f)
        f.close()
        
        self.locos = []
        for nr, loco_dict in enumerate(Config["locos"]):
            functions = [Function(self.unsaved_changes, *[function_dict[attrib] for attrib in self.function_attributes]) for function_dict in loco_dict["functions"]]
            speed_func = LinearSegmentFunction()
            speed_func.load(loco_dict["speed_control_points"])
            self.locos.append(Loco(self.unsaved_changes, functions, speed_func, *[loco_dict[attrib] for attrib in self.loco_attributes])) # TODO: sort entries of dict to match the Parameter-order but dont require all
        self.server = Server(self.unsaved_changes, *[Config["server"][attrib] for attrib in self.server_attributes])
        self.joystick = Joystick(self.unsaved_changes, *[Config["joystick"][attrib] for attrib in self.joystick_attributes])
        
        self.has_unsaved_changes = False
        self.save_opened_file(file_path)
        locked_print("Einstellungen wurden geladen aus " + file_path)
    
    def save_opened_file(self, file_path):
        if self.last_file != file_path:
            f = open("last_file.json", "w")
            json.dump({"last_file": file_path}, f, indent=2)
            f.close()
            self.last_file = file_path
        self.opened_file = file_path
        
    def set_unsaved_changes_method(self, method):
        self.new_unsaved_changes_method = method
        
    def unsaved_changes(self, obj, name, value):
        if self.notice_unsaved_changes:
            locked_print("Attribute '" + name + "' of object '" + str(obj) + "' has new value:", value)
            self.has_unsaved_changes = True
            if self.opened_file != None and hasattr(self, "new_unsaved_changes_method"): # if method has been setup, call it
                self.new_unsaved_changes_method()
