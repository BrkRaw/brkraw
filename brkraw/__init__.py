from .lib import *

__version__ = '0.3.9'
__all__ = ['BrukerLoader', '__version__']


def load(path):
    return BrukerLoader(path)
