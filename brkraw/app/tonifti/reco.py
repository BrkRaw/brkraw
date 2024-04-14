import warnings
import numpy as np
from pathlib import Path
from brkraw.api.pvobj import Parameter
from brkraw.api.brkobj.scan import ScanInfo
from brkraw.api.analyzer import ScanInfoAnalyzer, DataArrayAnalyzer, AffineAnalyzer


class RecoToNifti:
    def __init__(self, data_path:Path, visu_pars:Path, method:Path=None):
        """_summary_

        Args:
            data_path (str): path of '2dseq' file in reco_dir
            pars_path (str): path of 'visu_pars' file in reco_dir
        """
        self._load_arr(data_path)
        self._load_pars(visu_pars, method)
        self._set_info()
    
    def is_recotonifti(self):
        return True
        
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
    
    def _load_arr(self, data_path):
        self.fileobj = open(data_path, 'rb')
    
    def _load_pars(self, visu_pars, method):
        visu_str = self._open_as_string(visu_pars)
        visu_obj = Parameter(visu_str, name='visu_pars')
        if not len([k for k in visu_obj.keys() if 'visu' in k.lower()]):
            raise TypeError("The loaded file is incompatible with the expected 'visu_pars' file. "
                            "Please verify that the file path correctly points to a 'visu_pars' file.")
        self.visu_pars = visu_obj
        if method:
            method_str = self._open_as_string(method)
            method_obj = Parameter(method_str, name='method')
            if not len([k for k in method_obj.keys() if 'pvm_' in k.lower()]):
                raise TypeError("The loaded file is incompatible with the expected 'method' file. "
                                "Please verify that the file path correctly points to a 'method' file.")
            self.method = method_obj
        else:
            self.method = None
            warnings.warn("The 'RecoToNifti' object did not receive an input argument for the 'method' file. "
                          "As a result, the affine matrix may be inaccurate. "
                          "Please consider providing the 'method' file as input if possible.")

    @staticmethod
    def _open_as_fileobj(path: Path):
        return open(path, 'rb')
    
    @classmethod
    def _open_as_string(cls, path: Path):
        return cls._open_as_fileobj(path).read().decode('UTF-8').split('\n')
    
    def get_data_dict(self):
        data_info = DataArrayAnalyzer(self.analysed, self.fileobj)
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
    
    def get_affine_dict(self, subj_type:str|None=None, subj_position:str|None=None):
        affine_info = AffineAnalyzer(self.info)
        subj_type = subj_type or affine_info.subj_type
        subj_position = subj_position or affine_info.subj_position
        affine = affine_info.get_affine(subj_type, subj_position)
        return {
            "num_slicepacks": len(affine) if isinstance(affine, list) else 1,
            "affine": affine,
            "subj_type": subj_type,
            "subj_position": subj_position
        }
    
    def get_dataobj(self, scale_correction=True):
        data_dict = self.get_data_dict()
        if scale_correction:
            dataobj = data_dict['data_array'] * data_dict['data_slope'] + data_dict['data_offset']
        return dataobj
    
    def get_affine(self, subj_type:str|None=None, subj_position:str|None=None):
        return self.get_affine_dict(subj_type, subj_position)['affine']
