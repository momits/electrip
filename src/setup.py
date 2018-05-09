#!/usr/bin/env python2.7
# -*- coding: UTF 8 -*-

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
      package_data={'electrip': ['styles.css',
                                 'electrip.ui',
                                 'icons/arrows/*',
                                 'icons/circle.svg',
                                 'icons/circle_insensitive.svg',
                                 'icons/logo_icon_128.png',
                                 'icons/logo_icon_64.png',
                                 'icons/question_mark.svg',
                                 'icons/reload_graph.png',
                                 'icons/sound_bar_pane_handle3.png',
                                 'css/*.css']},
      install_requires=['pygobject', 'pygame'])
