from __future__ import annotations
import warnings
import numpy as np
from brkraw import config
from nibabel.nifti1 import Nifti1Image
from .header import Header
from brkraw.api.pvobj.base import BaseBufferHandler
from brkraw.api.data import Scan
from xnippy.snippet import PlugInSnippet
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, Union, Literal
    from typing import List
    from numpy.typing import NDArray
    from xnippy.types import ConfigManagerType


class BaseMethods(BaseBufferHandler):
    config: ConfigManagerType = config
    
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
    def update_nifti1header(scanobj: 'Scan', 
                            nifti1image: 'Nifti1Image', 
                            reco_id: Optional[int] = None, 
                            scale_mode: Optional[Literal['header', 'apply']] = None):
        if reco_id:
            scanobj.set_scaninfo(reco_id)
        scale_mode = scale_mode or 'header'
        return Header(scaninfo=scanobj.info, nifti1image=nifti1image, scale_mode=scale_mode).get()

    @staticmethod
    def get_nifti1image(scanobj: 'Scan', 
                        reco_id: Optional[int] = None, 
                        scale_mode: Optional[Literal['header', 'apply']] = None,
                        subj_type: Optional[str] = None, 
                        subj_position: Optional[str] = None,
                        plugin: Optional[Union['PlugInSnippet', str]] = None, 
                        plugin_kws: Optional[dict] = None) -> Optional[Union['Nifti1Image', List['Nifti1Image']]]:
        if plugin:
            if nifti1image := BaseMethods._bypass_method_via_plugin(scanobj=scanobj,
                                                                    subj_type=subj_type, subj_position=subj_position,
                                                                    plugin=plugin, plugin_kws=plugin_kws):
                return nifti1image
            else:
                return None
        else:
            scale_mode = scale_mode or 'header'
            scale_correction = 1 if scale_mode == 'apply' else 0
            dataobj = BaseMethods.get_dataobj(scanobj=scanobj, 
                                              reco_id=reco_id, 
                                              scale_correction=scale_correction)
            affine = BaseMethods.get_affine(scanobj=scanobj,
                                            reco_id=reco_id,
                                            subj_type=subj_type,
                                            subj_position=subj_position)
        return BaseMethods._assemble_nifti1image(dataobj, affine)
        
    @staticmethod
    def _bypass_method_via_plugin(scanobj: 'Scan', 
                                  subj_type: Optional[str] = None, 
                                  subj_position: Optional[str] = None,
                                  plugin: Optional[Union['PlugInSnippet', str]] = None, 
                                  plugin_kws: Optional[dict] = None) -> Optional[Nifti1Image]:
        if isinstance(plugin, str):
            plugin = BaseMethods._get_plugin_snippets_by_name(plugin)
        if isinstance(plugin, PlugInSnippet) and plugin.type == 'tonifti':
            print(f'++ Installed PlugIn: {plugin}')
            with plugin.set(pvobj=scanobj.pvobj, **plugin_kws) as p:
                nifti1image = p.get_nifti1image(subj_type=subj_type, subj_position=subj_position)
            return nifti1image
        else:
            fetcher = config.get_fetcher('plugin')
            warnings.warn("Failed. Given plugin not available, "
                          "please install local plugin or use from available on "
                          f"remote repository. -> {[p.name for p in fetcher.remote]}",
                          UserWarning)
            return None
    
    @staticmethod
    def _get_plugin_snippets_by_name(plugin: str):
        fetcher = config.get_fetcher('plugin')
        if not fetcher.is_cache:
            plugin = BaseMethods._filter_snippets_by_name(plugin, fetcher.local)
        if fetcher.is_cache or not isinstance(plugin, PlugInSnippet):
            plugin = BaseMethods._filter_snippets_by_name(plugin, fetcher.remote)
        return plugin
    
    @staticmethod
    def _filter_snippets_by_name(name:str, snippets: list):
        if filtered := [s for s in snippets if s.name == name]:
            return filtered[0]
        else:
            return name
            
    @staticmethod
    def _assemble_nifti1image(scanobj: 'Scan', 
                              dataobj: NDArray, 
                              affine: NDArray,
                              scale_mode: Optional[Literal['header', 'apply']] = None):
        if isinstance(dataobj, list):
            # multi-dataobj (e.g. msme)
            niis = BaseMethods._assemble_msme(dataobj, affine)
            return [BaseMethods.update_nifti1header(nifti1image=nii, 
                                                    scanobj=scanobj, 
                                                    scale_mode=scale_mode) for nii in niis]
        if isinstance(affine, list):
            # multi-slicepacks
            niis = BaseMethods._assemble_ms(dataobj, affine)
            return niis
        nii = Nifti1Image(dataobj=dataobj, affine=affine)
        return BaseMethods.update_nifti1header(nifti1image=nii,
                                               scanobj=scanobj,
                                               scale_mode=scale_mode)

    @staticmethod
    def _assemble_msme(dataobj: NDArray, affine: NDArray):
        affine = affine if isinstance(affine, list) else [affine for _ in range(len(dataobj))]
        return [Nifti1Image(dataobj=dobj, affine=affine[i]) for i, dobj in enumerate(dataobj)]

    @staticmethod
    def _assemble_ms(dataobj: NDArray, affine: NDArray):
        return [Nifti1Image(dataobj=dataobj[:,:,i,...], affine=aff) for i, aff in enumerate(affine)]
    
    def list_plugin(self):
        avail_dict = self.config.avail('plugin')
        return {'local': [s for s in avail_dict['local'] if s.type == 'tonifti'],
                'remote': [s for s in avail_dict['remote'] if s.type == 'tonifti']}