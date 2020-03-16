from .lib import *
# from .lib.ui import load

__all__ = ['BrukerLoader']
__version__ = '0.2.3'

def load(path):
    return BrukerLoader(path)
