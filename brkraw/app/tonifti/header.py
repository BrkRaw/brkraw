from __future__ import annotations
import warnings
from nibabel.nifti1 import Nifti1Header
from typing import TYPE_CHECKING, Union
if TYPE_CHECKING:
    from brkraw.api.data import ScanInfo
    from .base import ScaleMode


class Header:
    def __init__(self, scaninfo:'ScanInfo', scale_mode:Union['ScaleMode', int]):
        self.info = scaninfo
        self.scale_mode = int(scale_mode.value)
        self.nifti1header = Nifti1Header()
        self.nifti1header.default_x_flip = False
        self._set_scale_params()
        self._set_sliceorder()
        self._set_time_step()
        
    def _set_sliceorder(self):
        slice_order_scheme = self.info.slicepack['slice_order_scheme']
        if slice_order_scheme == 'User_defined_slice_scheme' or slice_order_scheme:
            slice_code = 0
        elif slice_order_scheme == 'Sequential':
            slice_code = 1
        elif slice_order_scheme == 'Reverse_sequential':
            slice_code = 2
        elif slice_order_scheme == 'Interlaced':
            slice_code = 3
        elif slice_order_scheme == 'Reverse_interlacesd':
            slice_code = 4
        elif slice_order_scheme == 'Angiopraphy':
            slice_code = 5
        else:
            slice_code = 0
        
        if slice_code == 0:
            warnings.warn(
                "Failed to identify compatible 'slice_code'. "
                "Please use this header information with care in case slice timing correction is needed."
            )
        self.nifti1header['slice_code'] = slice_code
    
    def _set_time_step(self):
        if self.info.cycle['num_cycles'] > 1:
            time_step = self.info.cycle['time_step']
            self.nifti1header['pixdim'][4] = time_step
            num_slices = self.info.slicepack['num_slices_each_pack'][0]
            self.nifti1header['slice_duration'] = time_step / num_slices
            
    def _set_scale_params(self):
        if self.scale_mode == 2:
            self.nifti1header['scl_slope'] = self.info.dataarray['slope']
            self.nifti1header['scl_inter'] = self.info.dataarray['offset']

    def get(self):
        return self.nifti1header