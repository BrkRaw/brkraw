#!/usr/scripts/env python
"""
Bruker PVdataset loader / converter
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
__url__ = 'https://github.com/dvm-shlee/bruker'

setup(name='bruker',
      version=__version__,
      description='Bruker PvDataset Loader',
      python_requires='>3.5, <3.8',
      author=__author__,
      author_email=__email__,
      url=__url__,
      license='GNLv3',
      packages=find_packages(),
      install_requires=['shleeh>=0.0.2',
                        'nibabel>=3.0.2',
                        'numpy>=1.18.2',
                        'pillow>=7.1.1',
                        'tqdm>=4.45.0',
                        'SimpleITK>=1.2.4',
                        'pandas>=1.0.3',
                        'openpyxl>=3.0.3',
                        'xlrd>=1.0.0'],
      entry_points={
          'console_scripts': [
              'brkraw=brkraw.scripts.brkraw:main',
              'brk-backup=brkraw.scripts.brk_backup:main',
          ],
      },
      classifiers=[
            # How mature is this project? Common values are
            #  3 - Alpha
            #  4 - Beta
            #  5 - Production/Stable
            'Development Status :: 4 - Beta',

            # Indicate who your project is intended for
            'Intended Audience :: Science/Research',
            'Topic :: Scientific/Engineering :: Medical Science Apps.',
            'Natural Language :: English',

            # Specify the Python version you support here. In particular, ensure
            # that you indicate whether you support Python 2, Python 3 or both
            'Programming Language :: Python :: 3.7'
      ],
      keywords = 'bruker data_handler converter administrator_tool'
     )
