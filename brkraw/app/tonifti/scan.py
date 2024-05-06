from __future__ import annotations
from collections import OrderedDict
from pathlib import Path
from brkraw.api.data import Scan
from brkraw.api.pvobj import PvScan, PvReco, PvFiles
from .base import BaseMethods
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Union, Optional, Literal
    from brkraw.api import PlugInSnippet
    from nibabel.nifti1 import Nifti1Image
    

class ScanToNifti(Scan, BaseMethods):
    def __init__(self, 
                 *paths: Path, 
                 scale_mode: Optional[Literal['header', 'apply']] = None, 
                 **kwargs):
        """_summary_

        Args:
            data_path (str): path of '2dseq' file in reco_dir
            pars_path (str): path of 'visu_pars' file in reco_dir
        """
        self.scale_mode = scale_mode
        if len(paths) == 0:
            super().__init__(**kwargs)
        else:
            if len(paths) == 1 and paths[0].is_dir():
                abspath = paths[0].absolute()
                print(abspath)
                if contents := self._is_pvscan(abspath):
                    pvobj = self._construct_pvscan(abspath, contents)                
                elif contents := self._is_pvreco(abspath):
                    pvobj = self._construct_pvreco(abspath, contents)
            else:
                pvobj = PvFiles(*paths)
            super().__init__(pvobj=pvobj, reco_id=pvobj._reco_id)

    @staticmethod
    def _construct_pvscan(path: 'Path', contents: 'OrderedDict') -> 'PvScan':
        ref_paths = (path.parent, path.name)
        scan_id = int(path.name) if path.name.isdigit() else None
        pvscan = PvScan(scan_id, ref_paths, contents)
        for reco_path in (path/'pdata').iterdir():
            if contents := ScanToNifti._is_pvreco(reco_path):
                reco_id = reco_path.name
                pvscan.set_reco(reco_path, reco_id, contents)
        return pvscan
    
    @staticmethod
    def _construct_pvreco(path: 'Path', contents: 'OrderedDict') -> 'PvReco':
        ref_paths = (path.parent, path.name)
        reco_id = int(path.name) if path.name.isdigit() else None
        return PvReco(None, reco_id, ref_paths, contents)
    
    @staticmethod
    def _is_pvscan(path: 'Path') -> Union[bool, 'OrderedDict']:
        if all([(path/f).exists() for f in ['method', 'acqp', 'pdata']]):
            contents = OrderedDict(dirs=[], files=[], file_indexes=[])
            for c in path.iterdir():
                if c.is_dir():
                    contents['dirs'].append(c.name)
                elif c.is_file():
                    contents['files'].append(c.name)
            return contents
        return False
    
    @staticmethod
    def _is_pvreco(path: 'Path') -> Union[bool, 'OrderedDict']:
        if all([(path/f).exists() for f in ['visu_pars', '2dseq']]):
            contents = OrderedDict(dirs=[], files=[], file_indexes=[])
            for c in path.iterdir():
                if c.is_dir():
                    contents['dirs'].append(c.name)
                elif c.is_file():
                    contents['files'].append(c.name)
            return contents
        return False
    
    def get_affine(self, reco_id: Optional[int] = None, 
                   subj_type: Optional[str] = None, 
                   subj_position: Optional[str] = None):
        return super().get_affine(scanobj = self, 
                                  reco_id = reco_id, 
                                  subj_type = subj_type, 
                                  subj_position = subj_position)
    
    def get_dataobj(self, reco_id: Optional[int] = None, 
                    scale_mode: Optional[Literal['header', 'apply']] = None):
        scale_mode = scale_mode or self.scale_mode
        scale_correction = False if not scale_mode or scale_mode == 'header' else True
        if reco_id:
            self.set_scaninfo(reco_id)
        return super().get_dataobj(scanobj = self, 
                                   reco_id = reco_id, 
                                   scale_correction = scale_correction)
    
    def get_data_dict(self, reco_id: Optional[int] = None):
        if reco_id:
            self.set_scaninfo(reco_id)
        return super().get_data_dict(scanobj=self, reco_id=reco_id)

    def get_affine_dict(self, reco_id: Optional[int] = None, 
                        subj_type: Optional[str] = None, 
                        subj_position: Optional[str] = None):
        if reco_id:
            self.set_scaninfo(reco_id)
        return super().get_affine_dict(scanobj = self, 
                                       reco_id = reco_id,
                                       subj_type = subj_type, 
                                       subj_position = subj_position)

    def update_nifti1header(self,
                            nifti1obj: 'Nifti1Image',
                            reco_id: Optional[int] = None, 
                            scale_mode: Optional[Literal['header', 'apply']] = None):
        scale_mode = scale_mode or self.scale_mode
        return super().update_nifti1header(self, nifti1obj, reco_id, scale_mode)

    def get_nifti1image(self, 
                        reco_id: Optional[int] = None, 
                        scale_mode: Optional[Literal['header', 'apply']] = None,
                        subj_type: Optional[str] = None, 
                        subj_position: Optional[str] = None,
                        plugin: Optional[Union['PlugInSnippet', str]] = None, 
                        plugin_kws: dict = None):
        scale_mode = scale_mode or self.scale_mode
        return super().get_nifti1image(self, 
                                       reco_id, 
                                       scale_mode, 
                                       subj_type, 
                                       subj_position, 
                                       plugin, 
                                       plugin_kws)