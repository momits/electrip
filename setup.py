#!/usr/bin/env python2.7
# -*- coding: UTF 8 -*-

from distutils.core import setup
from electrip.constants import ELECTRIP_VERSION

setup(name='Electrip',
      version=ELECTRIP_VERSION,
      description='Model railroad control using Gamepads',
      author='Moritz Renftle',
      url='http://www.electrip.sourceforge.net',
      license='GPL Version 3',
      
      packages=['electrip', 'electrip.config'],
      package_data={'electrip': ['styles.css',
                                 'electrip.ui',
                                 'icons/arrows/*',
                                 'icons/gamepads/*.png']})