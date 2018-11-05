#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import gettext
import logging
import sys

from electrip.electrip import Electrip
from electrip.constants import ELECTRIP_VERSION, LOCALE_PATH, APP_ID

_ = gettext.translation(APP_ID + "-main", localedir=LOCALE_PATH).gettext


"""
Starts Electrip.
"""

logging.basicConfig(format='%(message)s', level=logging.INFO)
logger = logging.getLogger()

if __name__ == "__main__":
    start_msg = _(" Starting Electrip Version {} ").format(ELECTRIP_VERSION)
    line = " " + "-" * len(start_msg) + " "
    logger.info(line + "\n|" + start_msg + "|\n" + line)

    app = Electrip()
    app.run(sys.argv)
