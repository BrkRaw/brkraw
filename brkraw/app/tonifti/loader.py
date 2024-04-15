from __future__ import annotations
from .brkraw import BrkrawToNifti
from .pvscan import PvScanToNifti
from .pvreco import PvRecoToNifti
from .pvfiles import PvFilesToNifti

class Loader:
    def __init__(self, *args, **kwargs):
        pass