#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ELECTRIP-Constants

# 0. ----------- General -----------

# 0.1. Version
ELECTRIP_VERSION = "3.1.5"

# 0.2. Icons
ICON_PATH_LIST = [
"Icons/logo_icon_128.png",
"Icons/logo_icon_64.png",
"Icons/logo_icon_32.png",
"Icons/logo_icon_16.png"
]

# 1. ----------- Configuration -----------

# 1.2 EntryTable
class EntryTableType:
    STRING = 0 # Entry for text
    INT = 1 # Entry for Integer
    FLOAT = 2 # Entry for Float
    COMBO = 3 # ComboBox
    BOOL = 4 # CheckButton
    FILE = 5 # Button that opens a file-selection-dialog

class SoundType:
    LOAD = "load"
    IDLE = "idle"
    ACCEL = "accel"
    DECEL = "decel"
    
class SegmentType:
    LOWER = 0
    MIDDLE = 1
    UPPER = 2

END_EVENT_LOWER_BOUND = 35
STOP_EVENT = 25
    