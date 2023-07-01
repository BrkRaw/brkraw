#!/usr/scripts/env python
"""
Bruker PVdataset loader / converter
"""
from distutils.core import setup
from setuptools import find_packages
import re
import io

__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
    io.open('brkraw/__init__.py', encoding='utf_8_sig').read()
    ).group(1)

__author__ = 'SungHo Lee'
__email__ = 'shlee@unc.edu'
__url__ = 'https://github.com/brkraw/brkraw'

setup(name='brkraw',
      version=__version__,
      description='Bruker PvDataset Loader',
      python_requires='>3.5',
      author=__author__,
      author_email=__email__,
      url=__url__,
      license='GNLv3',
      packages=find_packages(),
      install_requires=['nibabel>=3.0.2',
                        'numpy>=1.18.0',
                        'pandas>=1.0.0',
                        'pillow>=7.1.1',
                        'tqdm>=4.45.0',
                        'openpyxl>=3.0.3',
                        'xlrd>=1.0.0'],
      extras_require = {
          'SimpleITK':  ['SimpleITK>=1.2.4']
      },
      entry_points={
          'console_scripts': [
              'brkraw=brkraw.scripts.brkraw:main',
              'brk-backup=brkraw.scripts.brk_backup:main',
          ],
      },
      classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Intended Audience :: Science/Research',
            'Topic :: Scientific/Engineering :: Medical Science Apps.',
            'Natural Language :: English',
            'Programming Language :: Python :: >3.5'
      ],
      keywords = 'bruker data_handler converter administrator_tool'
     )
