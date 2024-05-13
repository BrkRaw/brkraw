from __future__ import annotations
from typing import TYPE_CHECKING
from .base import BaseHelper
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer

class SeqParams(BaseHelper):
    """_summary_
    Helper class to parse protocol parameters for data acqusition form 'acqp' file

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        
        acqp = analobj.acqp
        if not acqp:
            self._warn("Failed to fetch all Protocol information because the 'acqp' file is missing from 'analobj'.")
            
    def get_info(self):
        return {
        }