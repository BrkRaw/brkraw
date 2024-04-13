from __future__ import annotations
import re
import numpy as np
from typing import TYPE_CHECKING
from .base import BaseHelper
from .frame_group import FrameGroup
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer
    

class Cycle(BaseHelper):
    """
    Dependencies:
        FrameGroup
        visu_pars

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        scan_time = analobj.visu_pars.get("VisuAcqScanTime") or 0
        fg_info = analobj.get('info_frame_group') or FrameGroup(analobj).get_info()
        fg_not_slice = []
        if fg_info['type'] != None:
            fg_not_slice.extend([fg_info['shape'][id] for id, fg in enumerate(fg_info['id'])
                            if not re.search('slice', fg, re.IGNORECASE)])
        self.num_frames = np.prod(fg_not_slice) if len(fg_not_slice) else 1
        self.time_step = (scan_time / self.num_frames)
    
    def get_info(self):
        return {
            "num_frames": self.num_frames,
            "time_step": self.time_step,
            "unit": 'msec',
            'warns': self.warns
            }