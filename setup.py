#!/usr/bin/env python
"""
PyNIT (Python NeuroImaging Toolkit)
"""
from distutils.core import setup
from setuptools import find_packages
import re, io

__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
    io.open('brkraw/__init__.py', encoding='utf_8_sig').read()
    ).group(1)

__author__ = 'SungHo Lee'
__email__ = 'shlee@unc.edu'
__url__ = ''

setup(name='bruker',
      version=__version__,
      description='Bruker PvDataset Loader',
      author=__author__,
      author_email=__email__,
      url=__url__,
      license='GNLv3',
      packages=find_packages(),
      install_requires=['nibabel',
                        'numpy'
                         ],
      scripts=['brkraw/bin/brkraw',
               'brkraw/bin/brkraw-win.bat'
               ],
      classifiers=[
            # How mature is this project? Common values are
            #  3 - Alpha
            #  4 - Beta
            #  5 - Production/Stable
            'Development Status :: 5 - Production/Stable',

            # Indicate who your project is intended for
            'Framework :: Jupyter',
            'Intended Audience :: Science/Research',
            'Topic :: Scientific/Engineering :: Medical Science Apps.',
            'Natural Language :: English',

            # Specify the Python version you support here. In particular, ensure
            # that you indicate whether yoclu support Python 2, Python 3 or both
            'Programming Language :: Python :: 3.7'
      ],
      keywords = 'bruker'
     )
