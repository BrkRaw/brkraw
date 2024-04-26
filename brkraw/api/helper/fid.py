from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING
from .base import BaseHelper, BYTEORDER, WORDTYPE
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer


class FID(BaseHelper):
    """requires visu_pars and aqcp to parse parameter related to the dtype of binary files

    Dependencies:
        acqp
        visu_pars

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        acqp = analobj.acqp
        
        if acqp:
            word_type = f'_{"".join(acqp["ACQ_word_size"].split("_"))}_SGN_INT'
            byte_order = f'{acqp["BYTORDA"]}Endian'
            self.dtype = np.dtype(f'{BYTEORDER[byte_order]}{WORDTYPE[word_type]}')
        else:
            self.fid_dtype = None
            self._warn("Failed to fetch 'fid_dtype' information because the 'acqp' file is missing from 'analobj'.")


    def get_info(self):
        return {
            'dtype': self.dtype,
            'warns': self.warns
        }