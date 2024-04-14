from pathlib import Path
from brkraw.api.pvobj import PvFiles
from .base import BaseMethods, ScaleMode

class PvFilesToNifti(PvFiles, BaseMethods):
    def __init__(self, *files):
        """_summary_

        Args:
            data_path (str): path of '2dseq' file in reco_dir
            pars_path (str): path of 'visu_pars' file in reco_dir
        """
        super.__init__(*files)
        self._set_info()
    
