import numpy as np
from enum import Enum
from brkraw.api.loader import BrukerLoader

class ScaleMode(Enum):
    NONE = 0
    APPLY = 1
    HEADER = 2

class BrukerToNifti(BrukerLoader):
    def __init__(self, path):
        super().__init__(path)
        self._cache = {}
    
    def info(self):
        pass
    
    def get_scan(self, scan_id:int):
        if scan_id not in self._cache.keys():
            self._cache[scan_id] = super().get_scan(scan_id)
        return self._cache[scan_id]
    
    def get_pars(self, scan_id:int, reco_id:int|None=None):
        scanobj = self.get_scan(scan_id)
        return scanobj.get_info(reco_id, get_analyzer=True).get_pars(reco_id)
    
    def get_affine(self, scan_id:int, reco_id:int|None=None, subj_type:str|None=None, subj_position:str|None=None):
        return self.get_affine_dict(scan_id, reco_id, subj_type, subj_position)['affine']
    
    def get_dataobj(self, scan_id:int, reco_id:int|None=None, scale_mode:ScaleMode = ScaleMode.APPLY):
        if scale_mode == ScaleMode.HEADER:
            raise ValueError('HEADER not supported, use get_nifti1image instead')
        data_dict = self.get_data_dict(scan_id, reco_id)
        dataobj = data_dict['data_array']
        if scale_mode == ScaleMode.APPLY:
            dataslp = data_dict['data_slope']
            dataoff = data_dict['data_offset']
        return dataobj
    
    def get_data_dict(self, scan_id:int, reco_id:int|None=None):
        scanobj = self.get_scan(scan_id)
        data_info = scanobj.get_dataarray(reco_id, get_analyzer=True)
        axis_labels = data_info.shape_desc
        slice_axis = axis_labels.index('slice') if 'slice' in axis_labels else 2
        dataarray = scanobj.get_dataarray(reco_id)
        if slice_axis != 2:
            dataarray = np.swapaxes(dataarray, slice_axis, 2)
            axis_labels[slice_axis], axis_labels[2] = axis_labels[2], axis_labels[slice_axis]
        return {
            'data_array': dataarray,
            'data_slope': data_info.slope,
            'data_offset': data_info.offset,
            'axis_labels': axis_labels
        }      

    def get_affine_dict(self, scan_id:int, reco_id:int|None=None, subj_type:str|None=None, subj_position:str|None=None):
        scanobj = self.get_scan(scan_id)
        affine_info = scanobj.get_affine(reco_id, get_analyzer=True)
        subj_type = subj_type or affine_info.subj_type
        subj_position = subj_position or affine_info.subj_position
        affine = affine_info.get_affine(subj_type, subj_position)
        return {
            "num_slicepacks": len(affine) if isinstance(affine, list) else 1,
            "affine": affine,
            "subj_type": subj_type,
            "subj_position": subj_position
        }

    def get_bids_metadata(self, scan_id:int, reco_id:int|None=None, bids_recipe=None):
        pars = self.get_pars(scan_id, reco_id)

    def get_bdata(self, scan_id):
        method = self.get_pars(scan_id).method
        
    def get_nifti1header(self, scan_id:int, reco_id:int|None=None):
        pars = self.get_pars(scan_id, reco_id)

    def get_nifti1image(self, scan_id:int, reco_id:int|None=None, 
                        subj_type:str|None=None, subj_position:str|None=None, 
                        scale_mode:ScaleMode = ScaleMode.HEADER):
        data_dict = self.get_dataobj(scan_id, reco_id)
        affine_dict = self.get_affine(scan_id, reco_id, subj_type, subj_position)
        
        