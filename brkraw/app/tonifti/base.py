from __future__ import annotations
import warnings
import numpy as np
from pathlib import Path
from nibabel.nifti1 import Nifti1Image
from .header import Header
from brkraw import config
from brkraw.api.pvobj.base import BaseBufferHandler
from brkraw.api.pvobj import PvScan, PvReco, PvFiles
from brkraw.api.data import Scan
from brkraw.api.config.snippet import PlugInSnippet
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import List, Optional, Union, Literal
    from brkraw.api.config.manager import Manager as ConfigManager
    
    
XYZT_UNITS = \
    dict(EPI=('mm', 'sec'))


class BaseMethods(BaseBufferHandler):
    config: ConfigManager = config
    
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
                        plugin: Optional[Union['PlugInSnippet', str]] = None, 
                        plugin_kws: Optional[dict] = None) -> Union['Nifti1Image', List['Nifti1Image']]:
        if plugin:
            if isinstance(plugin, str):
                not_available = False
                fetcher = config.get_fetcher('plugin')
                # check plugin available on local
                if fetcher.is_cache:
                    # No plugin downloaded, check on remote
                    if available := [p for p in fetcher.remote if p.name == plugin]:
                        plugin = available.pop()
                    else:
                        not_available = True
                else:
                    if available := [p for p in fetcher.local if p.name == plugin]:
                        plugin = available.pop()
                    else:
                        not_available = True
            if isinstance(plugin, PlugInSnippet) and plugin.type == 'tonifti':
                with plugin.set(pvobj=scanobj.pvobj, **plugin_kws) as p:
                    dataobj = p.get_dataobj()
                    affine = p.get_affine(subj_type=subj_type, subj_position=subj_position)
                    header = p.get_nifti1header()
            else:
                not_available = True
            if not_available:
                warnings.warn("Failed. Given plugin not available, please install local plugin or use from available on "
                              f"remote repository. -> {[p.name for p in fetcher.remote]}",
                              UserWarning)
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
            header = BaseMethods.get_nifti1header(scanobj=scanobj,
                                                  reco_id=reco_id,
                                                  scale_mode=scale_mode)
        
        if isinstance(dataobj, list):
            # multi-dataobj (e.g. msme)
            affine = affine if isinstance(affine, list) else [affine for _ in range(len(dataobj))]
            return [Nifti1Image(dataobj=dobj, affine=affine[i], header=header) for i, dobj in enumerate(dataobj)]
        if isinstance(affine, list):
            # multi-slicepacks
            return [Nifti1Image(dataobj[:,:,i,...], affine=aff, header=header) for i, aff in enumerate(affine)]
        return Nifti1Image(dataobj=dataobj, affine=affine, header=header)
    
    
class BasePlugin(Scan, BaseMethods):
    """Base class for handling plugin operations, integrating scanning and basic method functionalities.

    This class initializes plugin operations with options for verbose output and integrates functionalities
    from the Scan and BaseMethods classes. It provides methods to close the plugin and clear any cached data.

    Args:
        pvobj (Union['PvScan', 'PvReco', 'PvFiles']): An object representing the PV (ParaVision) scan, reconstruction, 
                                                      or file data, which is central to initializing the plugin operations.
        verbose (bool): Flag to enable verbose output during operations, defaults to False.
        **kwargs: Additional keyword arguments that are passed to the superclass.

    Attributes:
        verbose (bool): Enables or disables verbose output.
    """
    def __init__(self, pvobj: Union['PvScan', 'PvReco', 'PvFiles'], 
                 verbose: bool=False, **kwargs):
        """Initializes the BasePlugin with a PV object, optional verbosity, and other parameters.

        Args:
            pvobj (Union['PvScan', 'PvReco', 'PvFiles']): The primary object associated with ParaVision operations.
            verbose (bool, optional): If True, enables verbose output. Defaults to False.
            **kwargs: Arbitrary keyword arguments passed to the superclass initialization.
        """
        super().__init__(pvobj, **kwargs)
        self.verbose = verbose
    
    def close(self):
        """Closes the plugin and clears any associated caches by invoking the clear_cache method.
        """
        super().close()
        self.clear_cache()
                
    def clear_cache(self):
        """Clears all cached data associated with the plugin. This involves deleting files that have been
        cached during plugin operations.
        """
        for buffer in self._buffers:
            file_path = Path(buffer.name)
            if file_path.exists():
                file_path.unlink()
