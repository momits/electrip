#!/bin/bash

# change to the directory this file is located within
cd ${0%/*};
# change into the electrip package
cd electrip;

# start electrip and pass all arguments to it
python main.py $*;
