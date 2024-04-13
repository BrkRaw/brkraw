from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING
from .base import BaseHelper
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer

class Image(BaseHelper):
    """
    Dependencies:
        visu_pars

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        visu_pars = analobj.visu_pars
        
        self.dim = visu_pars["VisuCoreDim"]
        self.dim_desc = visu_pars["VisuCoreDimDesc"]
        fov = visu_pars.get("VisuCoreExtent")
        shape = visu_pars.get("VisuCoreSize")
        self.resolusion = np.divide(fov, shape).tolist() if (fov and shape) else None
        self.field_of_view = fov
        self.shape = shape
        
        if self.dim > 3:
            self._warn('Image dimension exceeds 3. Ensure that handling of higher dimensions is supported and correctly implemented.')
        message = lambda x: f"The axis of the image includes '{x}' dimension, which is not limited to spatial types."
        if isinstance(self.dim_desc, list):
            for d in self.dim_desc:
                if d != 'spatial':
                    self._warn(message(d))
        elif isinstance(self.dim_desc, str):
            if self.dim_desc != 'spatial':
                self._warn(message(self.dim_desc)) 
    
    def get_info(self):
        return {
            'dim': self.dim,
            'dim_desc': self.dim_desc,
            'shape': self.shape,
            'resolution': self.resolusion,
            'field_of_view': self.field_of_view,
            'unit': 'mm',
            'warns': self.warns
        }