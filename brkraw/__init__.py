from .lib import *
from xnippet import XnippetManager

__version__ = '0.4.0'
config = XnippetManager(package_name=__package__, 
                       package_version=__version__,
                       package__file__=__file__,
                       config_filename='config.yaml')

__all__ = ['BrukerLoader', '__version__', 'config']

def load(path):
    return BrukerLoader(path)
