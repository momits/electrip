#!/bin/bash

# get the directory this file is located within
# and add it to PYTHONPATH
DIR=$( cd "$( dirname "${0}" )" && pwd );
export PYTHONPATH=${DIR}/src;

# start electrip and pass all arguments to it
python3 -m electrip $*;