from __future__ import annotations
from brkraw.api.brkobj import StudyObj
from .base import BaseMethods, ScaleMode
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pathlib import Path


class BrkrawToNifti(StudyObj, BaseMethods):
    def __init__(self, path:'Path', scale_mode: 'ScaleMode'|None = None):
        """_summary_

        Args:
            path (Path): _description_
            scale_mode (ScaleMode | None, optional): _description_. Defaults to None.
        """

        super().__init__(path)
        if scale_mode:
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
    
    def get_scan_analyzer(self, scan_id:int, reco_id:int|None=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int | None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        return self.get_scan(scan_id).get_info(reco_id, get_analyzer=True)
    
    def get_affine(self, scan_id:int, reco_id:int|None=None, subj_type:str|None=None, subj_position:str|None=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int | None, optional): _description_. Defaults to None.
            subj_type (str | None, optional): _description_. Defaults to None.
            subj_position (str | None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        scanobj = self.get_scan(scan_id)
        return super().get_affine(scanobj=scanobj, reco_id=reco_id, subj_type=subj_type, subj_position=subj_position)
    
    def get_dataobj(self, scan_id:int, reco_id:int|None=None, scale_mode:'ScaleMode'|None = None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int | None, optional): _description_. Defaults to None.
            scale_mode (ScaleMode&#39; | None, optional): _description_. Defaults to None.

        Raises:
            ValueError: _description_

        Returns:
            _type_: _description_
        """
        scale_mode = scale_mode or self.scale_mode
        if scale_mode == ScaleMode.HEADER:
            raise ValueError("The 'HEADER' option for scale_mode is not supported in this context. Only 'NONE' or 'APPLY' options are available. "
                             "To use the 'HEADER' option, please switch to the 'get_nifti1image' method, which supports storing scales in the header.")
        scanobj = self.get_scan(scan_id)
        return super().get_dataobj(scanobj=scanobj, fileobj=None, reco_id=reco_id, scale_correction=bool(scale_mode))
    
    def get_data_dict(self, scan_id:int, reco_id:int|None=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int | None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        scanobj = self.get_scan(scan_id)
        return super().get_data_dict(scanobj=scanobj, reco_id=reco_id)

    def get_affine_dict(self, scan_id:int, reco_id:int|None=None, subj_type:str|None=None, subj_position:str|None=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int | None, optional): _description_. Defaults to None.
            subj_type (str | None, optional): _description_. Defaults to None.
            subj_position (str | None, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        scanobj = self.get_scan(scan_id)
        return super().get_affine_dict(scanobj=scanobj, reco_id=reco_id,
                                       subj_type=subj_type, subj_position=subj_position)

    def get_nifti1header(self, scan_id:int, reco_id:int|None=None, scale_mode:'ScaleMode'|None = None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int | None, optional): _description_. Defaults to None.
            scale_mode (ScaleMode&#39; | None, optional): _description_. Defaults to None.

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

    def get_bids_metadata(self, scan_id:int, reco_id:int|None=None, bids_recipe=None):
        """_summary_

        Args:
            scan_id (int): _description_
            reco_id (int | None, optional): _description_. Defaults to None.
            bids_recipe (_type_, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        analobj = self.get_scan_analyzer(scan_id, reco_id)
        return super().get_bids_metadata(analobj, bids_recipe)    
    