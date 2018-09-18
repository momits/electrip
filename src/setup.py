#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup
from electrip.constants import ELECTRIP_VERSION


setup(name='Electrip',
      version=ELECTRIP_VERSION,
      description='Model railroad control using Gamepads',
      author='Moritz Renftle',
      url='http://www.electrip.sourceforge.net',
      license='GPL Version 3',

      package_dir={'': 'src'},
      packages=['electrip', 'electrip.config'],
      package_data={'electrip': ['electrip.ui',
                                 'locale/*/LC_MESSAGES/*.mo',
                                 'icons/arrows/*',
                                 'icons/circle.svg',
                                 'icons/circle_insensitive.svg',
                                 'icons/logo_icon_128.png',
                                 'icons/logo_icon_64.png',
                                 'icons/question_mark.svg',
                                 'icons/reload_graph.png',
                                 'icons/sound_segment_bar_handle.png',
                                 'css/*.css']},
      install_requires=['pycairo', 'PyGObject', 'Pygame==1.9.3'])
