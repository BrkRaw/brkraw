from __future__ import annotations
import warnings
import numpy as np
import nibabel as nib
from pathlib import Path
from .header import Header
from brkraw.api.pvobj.base import BaseBufferHandler
from brkraw.api.pvobj import PvScan, PvReco, PvFiles
from brkraw.api.data import Scan
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, Union, Literal
    from brkraw.api.plugin import Plugged
    
    
XYZT_UNITS = \
    dict(EPI=('mm', 'sec'))


class BaseMethods(BaseBufferHandler):
    def set_scale_mode(self, 
                       scale_mode: Optional[Literal['header', 'apply']] = None):
        self.scale_mode = scale_mode or 'header'
    
    @staticmethod
    def get_dataobj(scanobj:'Scan',
                    reco_id:Optional[int] = None,
                    scale_correction:bool = False):
        data_dict = BaseMethods.get_data_dict(scanobj, reco_id)
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
    def get_affine(scanobj:'Scan', reco_id: Optional[int] = None, 
                   subj_type: Optional[str]=None, 
                   subj_position: Optional[str]=None):
        return BaseMethods.get_affine_dict(scanobj, reco_id, 
                                           subj_type, subj_position)['affine']
    
    @staticmethod
    def get_data_dict(scanobj: 'Scan', 
                      reco_id: Optional[int] = None):
        datarray_analyzer = scanobj.get_datarray_analyzer(reco_id)
        axis_labels = datarray_analyzer.shape_desc
        dataarray = datarray_analyzer.get_dataarray()
        slice_axis = axis_labels.index('slice') if 'slice' in axis_labels else 2
        if slice_axis != 2:
            dataarray = np.swapaxes(dataarray, slice_axis, 2)
            axis_labels[slice_axis], axis_labels[2] = axis_labels[2], axis_labels[slice_axis]
        return {
            'data_array': dataarray,
            'data_slope': datarray_analyzer.slope,
            'data_offset': datarray_analyzer.offset,
            'axis_labels': axis_labels
        }
    
    @staticmethod
    def get_affine_dict(scanobj: 'Scan', reco_id: Optional[int] = None,
                        subj_type: Optional[str] = None, 
                        subj_position: Optional[str] = None):
        affine_analyzer = scanobj.get_affine_analyzer(reco_id)
        subj_type = subj_type or affine_analyzer.subj_type
        subj_position = subj_position or affine_analyzer.subj_position
        affine = affine_analyzer.get_affine(subj_type, subj_position)
        return {
            "num_slicepacks": len(affine) if isinstance(affine, list) else 1,
            "affine": affine,
            "subj_type": subj_type,
            "subj_position": subj_position
        }
        
    @staticmethod
    def get_nifti1header(scanobj: 'Scan', reco_id: Optional[int] = None, 
                         scale_mode: Optional[Literal['header', 'apply']] = None):
        if reco_id:
            scanobj.set_scaninfo(reco_id)
        scale_mode = scale_mode or 'header'
        return Header(scanobj.info, scale_mode).get()

    @staticmethod
    def get_nifti1image(scanobj: 'Scan', 
                        reco_id: Optional[int] = None, 
                        scale_mode: Optional[Literal['header', 'apply']] = None,
                        subj_type: Optional[str] = None, 
                        subj_position: Optional[str] = None,
                        plugin: Optional['Plugged'] = None, 
                        plugin_kws: dict = None):
        if plugin and plugin.type == 'tonifti':
            with plugin(scanobj, **plugin_kws) as p:
                dataobj = p.get_dataobj(bool(scale_mode))
                affine = p.get_affine(subj_type=subj_type, subj_position=subj_position)
                header = p.get_nifti1header()
        else:
            scale_mode = scale_mode or 'header'
            dataobj = BaseMethods.get_dataobj(scanobj, reco_id, bool(scale_mode))
            affine = BaseMethods.get_affine(scanobj, reco_id, subj_type, subj_position)
            header = BaseMethods.get_nifti1header(scanobj, reco_id, scale_mode)
        return nib.Nifti1Image(dataobj, affine, header)
    
    
class BasePlugin(Scan, BaseMethods):
    def __init__(self, pvobj: Union['PvScan', 'PvReco', 'PvFiles'], 
                 verbose: bool=False, **kwargs):
        super().__init__(pvobj, **kwargs)
        self.verbose = verbose
    
    def close(self):
        super().close()
        self.clear_cache()
                
    def clear_cache(self):
        for buffer in self._buffers:
            file_path = Path(buffer.name)
            if file_path.exists():
                file_path.unlink()
