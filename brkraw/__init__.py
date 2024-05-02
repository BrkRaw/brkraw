from .lib import *
from .api import ConfigManager

config = ConfigManager()
__version__ = '0.4.00'
__all__ = ['BrukerLoader', '__version__', 'config']


def load(path):
    return BrukerLoader(path)
