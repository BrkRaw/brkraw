from __future__ import annotations
from typing import TYPE_CHECKING
from .base import BaseHelper
from functools import reduce
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer
    

class FrameGroup(BaseHelper):
    """
    Dependencies:
        visu_pars  

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        visu_pars = analobj.visu_pars
        if visu_pars.get('VisuFGOrderDescDim'):
            self.exists = True
            self.type = visu_pars.get("VisuCoreFrameType")
            self.shape = []
            self.id = []
            self.comment = []
            self.dependent_vals = []
            for (shape, fgid, comment, vals_start, vals_cnt) in visu_pars["VisuFGOrderDesc"]:
                self.shape.append(shape)
                self.id.append(fgid)
                self.comment.append(comment)
                self.dependent_vals.append([
                    visu_pars["VisuGroupDepVals"][vals_start + count]
                        for count in range(vals_cnt)
                    ] if vals_cnt else [])
            self.size = reduce(lambda x, y: x * y, self.shape)
        else:
            self.exists = False
            self._warn("Unable to construct frame group information because 'VisuFGOrderDescDim' "
                       "was not found in the 'visu_pars' parameter file.")
            
    def get_info(self):
        if not self.exists:
            return {
                'type': None,
                'warns': self.warns
            }
        return {
            'type': self.type,
            'size': self.size,
            'shape': self.shape,
            'id': self.id,
            'comment': self.comment,
            'dependent_vals': self.dependent_vals,
            'warns': self.warns
            }