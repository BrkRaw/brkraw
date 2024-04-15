from __future__ import annotations
from .base import BaseAnalyzer
import numpy as np
from copy import copy
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..brkobj import ScanInfo
    from io import BufferedReader
    from zipfile import ZipExtFile


class DataArrayAnalyzer(BaseAnalyzer):
    def __init__(self, infoobj: 'ScanInfo', fileobj: BufferedReader|ZipExtFile):
        infoobj = copy(infoobj)
        self._parse_info(infoobj)
        self.buffer = fileobj

    def _parse_info(self, infoobj: 'ScanInfo'):
        if not hasattr(infoobj, 'dataarray'):
            raise AttributeError
        self.slope = infoobj.dataarray['2dseq_slope']
        self.offset = infoobj.dataarray['2dseq_offset']
        self.dtype = infoobj.dataarray['2dseq_dtype']
        self.shape = infoobj.image['shape'][:]
        self.shape_desc = infoobj.image['dim_desc'][:]
        if infoobj.frame_group and infoobj.frame_group['type']:
            self._calc_array_shape(infoobj)
            
    def _calc_array_shape(self, infoobj: 'ScanInfo'):
        self.shape.extend(infoobj.frame_group['shape'][:])
        self.shape_desc.extend([fgid.replace('FG_', '').lower() for fgid in infoobj.frame_group['id']])
    
    def get_dataarray(self):
        self.buffer.seek(0)
        return np.frombuffer(self.buffer.read(), self.dtype).reshape(self.shape, order='F')
