from __future__ import annotations
import os
from pathlib import Path
from brkraw.api.pvobj import PvReco
from .base import BaseMethods


class PvRecoToNifti(PvReco, BaseMethods):
    def __init__(self, path: 'Path'):
        """_summary_

        Args:
            data_path (str): path of '2dseq' file in reco_dir
            pars_path (str): path of 'visu_pars' file in reco_dir
        """
        rootpath, reco_path = os.path.split(path)
        _, dirs, files = os.walk(path)
        super.__init__(None, reco_path, (rootpath, reco_path), {'dirs':dirs, 'files':files})
        self._set_info()
