from __future__ import annotations
from pathlib import Path
from brkraw.api.data import Scan
from brkraw.api.pvobj import PvScan, PvReco, PvFiles
from collections import OrderedDict
from typing import TYPE_CHECKING
from .base import BaseMethods, ScaleMode
if TYPE_CHECKING:
    from typing import Union, Optional
    from brkraw.api.plugin import Plugged
    

class ScanToNifti(Scan, BaseMethods):
    def __init__(self, *paths: Path, **kwargs):
        """_summary_

        Args:
            data_path (str): path of '2dseq' file in reco_dir
            pars_path (str): path of 'visu_pars' file in reco_dir
        """
        if len(paths) == 0:
            super().__init__(**kwargs)
        if len(paths) == 1 and paths[0].is_dir():
            abspath = paths[0].absolute()
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
    
    def get_affine(self, reco_id:Optional[int]=None, 
                   subj_type:Optional[str]=None, subj_position:Optional[str]=None):
        return super().get_affine(scanobj=self, reco_id=reco_id, 
                                  subj_type=subj_type, subj_position=subj_position)
    
    def get_dataobj(self, reco_id:Optional[int]=None, scale_mode:Optional['ScaleMode'] = None):
        scale_mode = scale_mode or self.scale_mode
        scale_correction = False if scale_mode == ScaleMode.HEADER else True
        if reco_id:
            self._set_scaninfo(reco_id)
        return super().get_dataobj(scanobj=self, reco_id=reco_id, scale_correction=scale_correction)
    
    def get_data_dict(self, reco_id:Optional[int]=None):
        if reco_id:
            self._set_scaninfo(reco_id)
        return super().get_data_dict(scanobj=self, reco_id=reco_id)

    def get_affine_dict(self, reco_id:Optional[int]=None, subj_type:Optional[str]=None, subj_position:Optional[str]=None):
        if reco_id:
            self._set_scaninfo(reco_id)
        return super().get_affine_dict(scanobj=self, reco_id=reco_id,
                                       subj_type=subj_type, subj_position=subj_position)

    def get_nifti1header(self, reco_id:Optional[int]=None, scale_mode:Optional['ScaleMode'] = None):
        scale_mode = scale_mode or self.scale_mode
        if reco_id:
            self._set_scaninfo(reco_id)
        return super().get_nifti1header(self, scale_mode).get()

    def get_nifti1image(self, scan_id:int, reco_id:Optional[int]=None, scale_mode:Optional['ScaleMode']=None,
                        subj_type:Optional[str]=None, subj_position:Optional[str]=None,
                        plugin:Optional['Plugged']=None, plugin_kws:dict=None):
        scale_mode = scale_mode or self.scale_mode
        scanobj = self.get_scan(scan_id, reco_id)
        return super().get_nifti1image(scanobj, reco_id, scale_mode, subj_type, subj_position, plugin, plugin_kws)