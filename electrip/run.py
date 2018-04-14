#!/usr/bin/env python3
# -*- coding: UTF 8 -*-
import logging
import sys

from electrip.main import Electrip
from electrip.constants import ELECTRIP_VERSION

"""
Starts Electrip.
"""

logger = logging.Logger("electrip.main")

if __name__ == "__main__":
    start_msg = " Starting Electrip Version " + ELECTRIP_VERSION + " "
    line = " " + "-" * len(start_msg) + " "
    logger.info(line + "\n|" + start_msg + "|\n" + line)
    app = Electrip()
    app.run(sys.argv)
