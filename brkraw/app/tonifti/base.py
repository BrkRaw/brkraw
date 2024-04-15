from __future__ import annotations
from enum import Enum
import warnings
import numpy as np
from io import BufferedReader
from zipfile import ZipExtFile
from brkraw.api.brkobj import ScanObj, ScanInfo
from brkraw.api.analyzer import ScanInfoAnalyzer, DataArrayAnalyzer, AffineAnalyzer
from .header import Header
from typing import TYPE_CHECKING, Optional, Union
if TYPE_CHECKING:
    from pathlib import Path
    
    
XYZT_UNITS = \
    dict(EPI=('mm', 'sec'))


class ScaleMode(Enum):
    NONE = 0
    APPLY = 1
    HEADER = 2
    

class BaseMethods:
    info, fileobj = (None, None)
    
    def set_scale_mode(self, scale_mode:Optional[ScaleMode]=None):
        if scale_mode:
            self.scale_mode = scale_mode
        else:
            self.scale_mode = ScaleMode.HEADER
            
    def _set_info(self):
        analysed = ScanInfoAnalyzer(self)
        infoobj = ScanInfo()
        
        for attr_name in dir(analysed):
            if 'info_' in attr_name:
                attr_vals = getattr(analysed, attr_name)
                setattr(infoobj, attr_name.replace('info_', ''), attr_vals)
                if attr_vals and attr_vals['warns']:
                    infoobj.warns.extend(attr_vals['warns'])
        self.info = infoobj
        self.analysed = analysed
    
    @staticmethod
    def get_dataobj(scanobj:Union['ScanInfo','ScanObj'], 
                    fileobj:Union['BufferedReader', 'ZipExtFile', None] = None, 
                    reco_id:Optional[int] = None,
                    scale_correction:bool = False):
        data_dict = BaseMethods.get_data_dict(scanobj, fileobj, reco_id)
        dataobj = data_dict['data_array']
        if scale_correction:
            try:
                dataobj = dataobj * data_dict['data_slope'] + data_dict['data_offset']
            except ValueError as e:
                warnings.warn(
                    "Scale correction not applied. The 'slope' and 'offset' provided are not in a tested condition. "
                    "For further assistance, contact the developer via issue at: https://github.com/brkraw/brkraw.git",
                    UserWarning)
        return dataobj
    
    @staticmethod
    def get_affine(scanobj:Union['ScanInfo', 'ScanObj'], reco_id:Optional[int] = None, 
                   subj_type:Optional[str]=None, subj_position:Optional[str]=None):
        return BaseMethods.get_affine_dict(scanobj, reco_id, subj_type, subj_position)['affine']
    
    @staticmethod
    def get_data_dict(scanobj:Union['ScanInfo', 'ScanObj'], 
                      fileobj:Union['BufferedReader', 'ZipExtFile'] = None, 
                      reco_id:Optional[int] = None):
        if isinstance(scanobj, ScanObj):
            data_info = scanobj.get_data_info(reco_id)
        elif isinstance(scanobj, ScanInfo) and isinstance(scanobj, Union[BufferedReader, ZipExtFile]):
            data_info = DataArrayAnalyzer(scanobj, fileobj)
        else:
            raise TypeError(
                "Unsupported type for 'scanobj'. Expected 'scanobj' to be an instance of 'ScanObj' or "
                "'ScanInfo' combined with either 'BufferedReader' or 'ZipExtFile'. Please check the type of 'scanobj' "
                "and ensure it matches the expected conditions."
            )
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
    
    @staticmethod
    def get_affine_dict(scanobj:Union['ScanInfo','ScanObj'], reco_id:Optional[int] = None,
                        subj_type:Optional[str] = None, subj_position:Optional[str] = None):
        if isinstance(scanobj, ScanObj):
            affine_info = scanobj.get_affine_info(reco_id)
        elif isinstance(scanobj, ScanInfo):
            affine_info = AffineAnalyzer(scanobj)
        else:
            raise TypeError(
                "Unsupported type for 'scanobj'. Expected 'scanobj' to be an instance of 'ScanObj' or 'ScanInfo'. "
                "Please check the type of 'scanobj' and ensure it matches the expected conditions."
            )
        subj_type = subj_type or affine_info.subj_type
        subj_position = subj_position or affine_info.subj_position
        affine = affine_info.get_affine(subj_type, subj_position)
        return {
            "num_slicepacks": len(affine) if isinstance(affine, list) else 1,
            "affine": affine,
            "subj_type": subj_type,
            "subj_position": subj_position
        }
    
    @staticmethod
    def get_bdata(analobj:'ScanInfoAnalyzer'):
        """Extract, format, and return diffusion bval and bvec"""
        bvals = np.array(analobj.method.get('PVM_DwEffBval'))
        bvecs = np.array(analobj.method.get('PVM_DwGradVec').T)
        # Correct for single b-vals
        if np.size(bvals) < 2:
            bvals = np.array([bvals])
        # Normalize bvecs
        bvecs_axis = 0
        bvecs_L2_norm = np.atleast_1d(np.linalg.norm(bvecs, 2, bvecs_axis))
        bvecs_L2_norm[bvecs_L2_norm < 1e-15] = 1
        bvecs = bvecs / np.expand_dims(bvecs_L2_norm, bvecs_axis)
        return bvals, bvecs
    
    @staticmethod
    def get_bids_metadata(scaninfo:'ScanInfo', bids_recipe:Optional['Path']=None):
        print(isinstance(scaninfo, ScanInfo), bids_recipe)
        
    @staticmethod
    def get_nifti1header(scaninfo:'ScanInfo', scale_mode:Optional['ScaleMode']=None):
        scale_mode = scale_mode or ScaleMode.HEADER
        return Header(scaninfo, scale_mode).get()
        
    # @staticmethod
    # def get_nifti1image(self, scan_id:int, reco_id:int|None=None, 
    #                     subj_type:str|None=None, subj_position:str|None=None, 
    #                     scale_mode:ScaleMode = ScaleMode.HEADER):
    #     smode = scale_mode if scale_mode == ScaleMode.APPLY else ScaleMode.NONE
    #     data_dict = self.get_dataobj(scan_id, reco_id, smode)
    #     affine_dict = self.get_affine(scan_id, reco_id, subj_type, subj_position)