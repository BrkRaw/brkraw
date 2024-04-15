from __future__ import annotations
from brkraw.api.brkobj import StudyObj
from .base import BaseMethods, ScaleMode
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from pathlib import Path


class BrkrawToNifti(StudyObj, BaseMethods):
    def __init__(self, path:'Path', scale_mode: Optional['ScaleMode'] = None):
        """_summary_

        Args:
            path (Path): _description_
            scale_mode (ScaleMode , None, optional): _description_. Defaults to None.
        """

        super().__init__(path)
        self.set_scale_mode(scale_mode)
        self._cache = {}
    
    def get_scan(self, scan_id:int):
        """_summary_

        Args:
            scan_id (int): _description_

        Returns:
            _type_: _description_
        """
        if scan_id not in self._cache.keys():
            self._cache[scan_id] = super().get_scan(scan_id)
        return self._cache[scan_id]
    
    def get_scan_analyzer(self, scan_id:int, reco_id:Optional[int]=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int , None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        return self.get_scan(scan_id).get_info(reco_id, get_analyzer=True)
    
    def get_affine(self, scan_id:int, reco_id:Optional[int]=None, subj_type:Optional[str]=None, subj_position:Optional[str]=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int , None, optional): _description_. Defaults to None.
            subj_type (str , None, optional): _description_. Defaults to None.
            subj_position (str , None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        scanobj = self.get_scan(scan_id)
        return super().get_affine(scanobj=scanobj, reco_id=reco_id, subj_type=subj_type, subj_position=subj_position)
    
    def get_dataobj(self, scan_id:int, reco_id:Optional[int]=None, scale_mode:Optional['ScaleMode'] = None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int , None, optional): _description_. Defaults to None.
            scale_mode (ScaleMode; , None, optional): _description_. Defaults to None.

        Raises:
            ValueError: _description_

        Returns:
            _type_: _description_
        """
        scale_mode = scale_mode or self.scale_mode
        scale_correction = False if scale_mode == ScaleMode.HEADER else True
        scanobj = self.get_scan(scan_id)
        return super().get_dataobj(scanobj=scanobj, fileobj=None, reco_id=reco_id, scale_correction=scale_correction)
    
    def get_data_dict(self, scan_id:int, reco_id:Optional[int]=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int , None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        scanobj = self.get_scan(scan_id)
        return super().get_data_dict(scanobj=scanobj, reco_id=reco_id)

    def get_affine_dict(self, scan_id:int, reco_id:Optional[int]=None, subj_type:Optional[str]=None, subj_position:Optional[str]=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int , None, optional): _description_. Defaults to None.
            subj_type (str , None, optional): _description_. Defaults to None.
            subj_position (str , None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        scanobj = self.get_scan(scan_id)
        return super().get_affine_dict(scanobj=scanobj, reco_id=reco_id,
                                       subj_type=subj_type, subj_position=subj_position)

    def get_nifti1header(self, scan_id:int, reco_id:Optional[int]=None, scale_mode:Optional['ScaleMode'] = None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int , None, optional): _description_. Defaults to None.
            scale_mode (ScaleMode , None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        scale_mode = scale_mode or self.scale_mode
        scaninfo = self.get_scan(scan_id).get_info(reco_id)
        return super().get_nifti1header(scaninfo, scale_mode).get()
    
    def get_bdata(self, scan_id:int):
        """_summary_

        Args:
            scan_id (int): _description_

        Returns:
            _type_: _description_
        """
        analobj = self.get_scan_analyzer(scan_id)
        return super().get_bdata(analobj)

    def get_bids_metadata(self, scan_id:int, reco_id:Optional[int]=None, bids_recipe=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int , None, optional): _description_. Defaults to None.
            bids_recipe (_type_, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        analobj = self.get_scan_analyzer(scan_id, reco_id)
        return super().get_bids_metadata(analobj, bids_recipe)    
    