import warnings
from functools import partial

WORDTYPE = \
    dict(_32BIT_SGN_INT     = 'i',
         _16BIT_SGN_INT     = 'h',
         _8BIT_UNSGN_INT    = 'B',
         _32BIT_FLOAT       = 'f')
    
BYTEORDER = \
    dict(littleEndian       = '<',
         bigEndian          = '>')


def is_all_element_same(listobj):
    if listobj is None:
        return True
    else:
        return all(map(partial(lambda x, y: x == y, y=listobj[0]), listobj))

class BaseHelper:
    def __init__(self):
        self.warns = []
        
    def _warn(self, message):
        warnings.warn(message, UserWarning)
        self.warns.append(message)
        
    def get(self, attr):
        return getattr(self, attr) if hasattr(self, attr) else None
    
