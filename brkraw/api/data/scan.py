from __future__ import annotations
from typing import Optional, Union
import ctypes
from ..pvobj import PvScan, PvReco, PvFiles
from ..analyzer import ScanInfoAnalyzer, AffineAnalyzer, DataArrayAnalyzer, BaseAnalyzer


class ScanInfo(BaseAnalyzer):
    def __init__(self):
        self.warns = []
        
    @property
    def num_warns(self):
        return len(self.warns)
    

class Scan:
    """The Scan class design to interface with analyzer, 

    Args:
        pvobj (_type_): _description_
    """
    def __init__(self, pvobj: Union['PvScan', 'PvReco', 'PvFiles'], reco_id: Optional[int] = None,
                 loader_address: Optional[int] = None, debug: bool=False):
        self.reco_id = reco_id
        self._loader_address = loader_address
        self._pvobj_address = id(pvobj)
        self.is_debug = debug
        self._set_info()
    
    def retrieve_pvobj(self):
        if self._pvobj_address:
            return ctypes.cast(self._pvobj_address, ctypes.py_object).value
    
    def retrieve_loader(self):
        if self._loader_address:
            return ctypes.cast(self._loader_address, ctypes.py_object).value
    
    def _set_info(self):
        self.info = self.get_info(self.reco_id)
                
    def get_info(self, reco_id:Optional[int] = None, get_analyzer:bool = False):
        infoobj = ScanInfo()
        pvobj = self.retrieve_pvobj()
        analysed = ScanInfoAnalyzer(pvobj, reco_id, self.is_debug)
        
        if get_analyzer:
            return analysed
        for attr_name in dir(analysed):
            if 'info_' in attr_name:
                attr_vals = getattr(analysed, attr_name)
                if warns:= attr_vals.pop('warns', None):
                    infoobj.warns.extend(warns)
                setattr(infoobj, attr_name.replace('info_', ''), attr_vals)
        return infoobj
    
    def get_affine_analyzer(self, reco_id:Optional[int] = None):
        if reco_id:
            info = self.get_info(reco_id)
        else:
            info = self.info if hasattr(self, 'info') else self.get_info(self.reco_id)
        return AffineAnalyzer(info)
    
    def get_datarray_analyzer(self, reco_id: Optional[int] = None):
        pvobj = self.retrieve_pvobj()
        if isinstance(pvobj, PvScan):
            reco_id = reco_id or pvobj.avail[0]
            recoobj = pvobj.get_reco(reco_id)
            fileobj = recoobj.get_2dseq()
        else:
            fileobj = pvobj.get_2dseq()
        info = self.info if hasattr(self, 'info') else self.get_info(self.reco_id)
        return DataArrayAnalyzer(info, fileobj)
    
    def get_affine(self, reco_id:Optional[int] = None, 
                   subj_type:Optional[str] = None, subj_position:Optional[str] = None):
        return self.get_affine_analyzer(reco_id).get_affine(subj_type, subj_position)
    
    def get_dataarray(self, reco_id: Optional[int] = None):
        return self.get_datarray_analyzer(reco_id).get_dataarray()
    
    @property
    def pvobj(self):
        return self.retrieve_pvobj()
    
    @property
    def about_scan(self):
        return self.info.to_dict()
    
    @property
    def about_affine(self):
        return self.get_affine_analyzer().to_dict()
    
    @property
    def about_dataarray(self):
        return self.get_datarray_analyzer().to_dict()