#!/usr/bin/env python2.7
# -*- coding: UTF 8 -*-

import sys

from electrip.main import Electrip
from electrip.concurrent import locked_print
from electrip.constants import ELECTRIP_VERSION

"""
Starts Electrip.
"""

if __name__ == "__main__":
    start_msg = " Starting Electrip Version "+ ELECTRIP_VERSION + " "
    line = " " + "-" * len(start_msg) + " "
    locked_print(line + "\n|" + start_msg + "|\n" + line)
    app = Electrip()
    app.run(sys.argv)
