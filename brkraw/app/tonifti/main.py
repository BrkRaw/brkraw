import warnings
import numpy as np
from enum import Enum
from brkraw.api.loader import BrkrawLoader


XYZT_UNITS = \
    dict(EPI=('mm', 'sec'))


class ScaleMode(Enum):
    NONE = 0
    APPLY = 1
    HEADER = 2


class BrkrawToNifti1(BrkrawLoader):
    def __init__(self, path):
        super().__init__(path)
        self._cache = {}
    
    def info(self):
        pass
    
    def get_scan(self, scan_id:int):
        if scan_id not in self._cache.keys():
            self._cache[scan_id] = super().get_scan(scan_id)
        return self._cache[scan_id]
    
    def get_scan_info(self, scan_id:int, reco_id:int|None=None):
        scanobj = self.get_scan(scan_id)
        return scanobj.get_info(reco_id, get_analyzer=True)
    
    def get_affine(self, scan_id:int, reco_id:int|None=None, subj_type:str|None=None, subj_position:str|None=None):
        return self.get_affine_dict(scan_id, reco_id, subj_type, subj_position)['affine']
    
    def get_dataobj(self, scan_id:int, reco_id:int|None=None, scale_mode:ScaleMode = ScaleMode.APPLY):
        if scale_mode == ScaleMode.HEADER:
            raise ValueError("The 'HEADER' option for scale_mode is not supported in this context. Only 'NONE' or 'APPLY' options are available. "
                             "To use the 'HEADER' option, please switch to the 'get_nifti1image' method, which supports storing scales in the header.")
        data_dict = self.get_data_dict(scan_id, reco_id)
        dataobj = data_dict['data_array']
        return dataobj
    
    def get_data_dict(self, scan_id:int, reco_id:int|None=None):
        scanobj = self.get_scan(scan_id)
        data_info = scanobj.get_data_info(reco_id)
        axis_labels = data_info.shape_desc
        dataarray = data_info.get_dataarray()
        slice_axis = axis_labels.index('slice') if 'slice' in axis_labels else 2
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
        affine_info = scanobj.get_affine_info(reco_id)
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
        pars = self.get_scan_info(scan_id, reco_id)

    def get_bdata(self, scan_id):
        """Extract, format, and return diffusion bval and bvec"""
        info = self.get_scan_info(scan_id)
        bvals = np.array(info.method.get('PVM_DwEffBval'))
        bvecs = np.array(info.method.get('PVM_DwGradVec').T)
        # Correct for single b-vals
        if np.size(bvals) < 2:
            bvals = np.array([bvals])
        # Normalize bvecs
        bvecs_axis = 0
        bvecs_L2_norm = np.atleast_1d(np.linalg.norm(bvecs, 2, bvecs_axis))
        bvecs_L2_norm[bvecs_L2_norm < 1e-15] = 1
        bvecs = bvecs / np.expand_dims(bvecs_L2_norm, bvecs_axis)
        return bvals, bvecs
        
    def get_nifti1header(self, scan_id:int, reco_id:int|None=None):
        pars = self.get_pars(scan_id, reco_id)

    def get_nifti1image(self, scan_id:int, reco_id:int|None=None, 
                        subj_type:str|None=None, subj_position:str|None=None, 
                        scale_mode:ScaleMode = ScaleMode.HEADER):
        smode = scale_mode if scale_mode == ScaleMode.APPLY else ScaleMode.NONE
        data_dict = self.get_dataobj(scan_id, reco_id, smode)
        affine_dict = self.get_affine(scan_id, reco_id, subj_type, subj_position)
        
        