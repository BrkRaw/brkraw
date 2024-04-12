from __future__ import annotations
import re
from brkraw.api import helper
import numpy as np
from copy import copy
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .pvobj import PvScan
    from .loader import ScanInfo
    from io import BufferedReader
    from zipfile import ZipExtFile

SLICEORIENT = {
    0: 'sagital', 
    1: 'coronal', 
    2: 'axial'
    }

SUBJTYPE = ['Biped', 'Quadruped', 'Phantom', 'Other', 'OtherAnimal']
SUBJPOSE = {
    'part': ['Head', 'Foot', 'Tail'],
    'side': ['Supine', 'Prone', 'Left', 'Right']
}

class Pars:
    def __init__(self):
        pass
    
class ScanInfoAnalyzer:
    """Helps parse metadata from multiple parameter files to make it more human-readable.

    Args:
        pvscan (PvScan): The PvScan object containing acquisition and method parameters.
        reco_id (int, optional): The reconstruction ID. Defaults to None.

    Raises:
        NotImplementedError: If an operation is not implemented.
    """
    def __init__(self, pvscan: 'PvScan', reco_id:int|None = None):
        self.pars = self.get_pars(pvscan, reco_id)
        self.info_protocol = helper.Protocol(self).get_info()
        if self.pars.visu:
            self._set_attrs()
            self.info_dataarray = helper.DataArray(self).get_info()
            self.info_frame_group = helper.FrameGroup(self).get_info()
            self.info_image = helper.Image(self).get_info()
            self.info_slicepack = helper.SlicePack(self).get_info()
            self.info_cycle = helper.Cycle(self).get_info()
            if self.info_image['dim'] > 1:
                self.info_orientation = helper.Orientation(self).get_info()
    
    @staticmethod
    def get_pars(pvscan: 'PvScan', reco_id: int|None):
        pars = Pars()
        for p in ['acqp', 'method']:
            vals = getattr(pvscan, p)
            setattr(pars, p, vals)
        try:
            visu = pvscan.get_visu_pars(reco_id)
        except FileNotFoundError:
            visu = None
        setattr(pars, 'visu', visu)
        return pars
    
    def _set_attrs(self):
        """
        Parse parameters and set attributes from acqp, method, and visu_pars files.
        This function parses parameters from different objects (acqp, method, visu_pars) and sets corresponding attributes in the instance.
        Only attributes with prefixes 'Visu', 'PVM_', 'ACQ_' are set as object attributes in snake case to follow Pythonic naming conventions.

        Args:
            pvscan: The pvscan parameter.
            reco_id: The reco_id parameter.
        """
        for prefix, pars_obj in {'Visu': self.pars.visu, 
                                 'PVM_': self.pars.method, 
                                 'ACQ_': self.pars.acqp}.items():
            for key in pars_obj.keys():
                if prefix in key:
                    attr = self._camel_to_snake_case(key.replace(prefix, ''))
                    value = getattr(pars_obj, key)
                    attr = f'{prefix.lower()}{attr}' if '_' in prefix else f'{prefix.lower()}_{attr}'
                    setattr(self, attr, value)
        
    @staticmethod
    def _camel_to_snake_case(input_string: str):
        matches = re.finditer(r'[A-Z]+[^A-Z]*', input_string)
        output_string = []
        for m in matches:
            string = m.group()
            is_upper = [bool(char.isupper()) for char in string]
            if sum(is_upper) > 1 and not all(is_upper):
                idx_for_space = is_upper.index(False)
                output_string.append(f'{string[:idx_for_space-1]}_{string[idx_for_space-1:]}'.lower())
            else:
                output_string.append(string.lower())
        return '_'.join(output_string)
    
    def __dir__(self):
        return [attr for attr in self.__dict__.keys() if 'info_' in attr]
    
    
class AffineAnalyzer:
    def __init__(self, infoobj: 'ScanInfo'):
        infoobj = copy(infoobj)
        if infoobj.image['dim'] == 2:
            xr, yr = infoobj.image['resolution']
            self.resolution = [(xr, yr, zr) for zr in infoobj.slicepack['slice_distances_each_pack']]
        elif self.info.image['dim'] == 3:
            self.resolution = infoobj.image['resolution'][:]
        else:
            raise NotImplementedError
        if infoobj.slicepack['num_slice_packs'] > 1:
            self.affine = [
                self._calculate_affine(infoobj, slicepack_id)
                for slicepack_id in range(infoobj.slicepack['num_slice_packs'])
            ]
        else:
            self.affine = self._calculate_affine(infoobj)
        
        self.subj_type = infoobj.orientation['subject_type'] if hasattr(infoobj, 'orientation') else None
        self.subj_position = infoobj.orientation['subject_position'] if hasattr(infoobj, 'orientation') else None
        
    def get_affine(self, subj_type:str|None=None, subj_position:str|None=None):
        subj_type = subj_type or self.subj_type
        subj_position = subj_position or self.subj_position
        if isinstance(self.affine, list):
            affine = [self._correct_orientation(aff, subj_position, subj_type) for aff in self.affine]
        elif isinstance(self.affine, np.ndarray):
            affine = self._correct_orientation(self.affine, subj_position, subj_type)
        return affine
            
    def _calculate_affine(self, infoobj: 'ScanInfo', slicepack_id:int|None = None):
        sidx = infoobj.orientation['orientation_desc'][slicepack_id].index(2) \
            if slicepack_id else infoobj.orientation['orientation_desc'].index(2)
        slice_orient = SLICEORIENT[sidx]
        resol = self.resolution[slicepack_id] \
            if slicepack_id else self.resolution[0]
        orientation = infoobj.orientation['orientation'][slicepack_id] \
            if slicepack_id else infoobj.orientation['orientation']
        volume_origin = infoobj.orientation['volume_origin'][slicepack_id] \
            if slicepack_id else infoobj.orientation['volume_origin']
        if infoobj.slicepack['reverse_slice_order']:
            slice_distance = infoobj.slicepack['slice_distances_each_pack'][slicepack_id] \
                if slicepack_id else infoobj.slicepack['slice_distances_each_pack']
            volume_origin = self._correct_origin(orientation, volume_origin, slice_distance)
        return self._compose_affine(resol, orientation, volume_origin, slice_orient)
    
    @staticmethod
    def _correct_origin(orientation, volume_origin, slice_distance):
        new_origin = orientation.dot(volume_origin)
        new_origin[-1] += slice_distance
        return orientation.T.dot(new_origin)
    
    @staticmethod
    def _compose_affine(resolution, orientation, volume_origin, slice_orient):
        resol = np.array(resolution)
        if slice_orient in ['axial', 'sagital']:
            resol = np.diag(resol)
        else:
            resol = np.diag(resol * np.array([1, 1, -1]))
        
        rmat = orientation.T.dot(resol)
        return helper.from_matvec(rmat, volume_origin)
    
    @staticmethod
    def _est_rotate_angle(subj_pose):
        rotate_angle = {'rad_x':0, 'rad_y':0, 'rad_z':0}
        if subj_pose:
            if subj_pose == 'Head_Supine':
                rotate_angle['rad_z'] = np.pi
            elif subj_pose == 'Head_Prone':
                pass
            elif subj_pose == 'Head_Left':
                rotate_angle['rad_z'] = np.pi/2
            elif subj_pose == 'Head_Right':
                rotate_angle['rad_z'] = -np.pi/2
            elif subj_pose in ['Foot_Supine', 'Tail_Supine']:
                rotate_angle['rad_x'] = np.pi
            elif subj_pose in ['Foot_Prone', 'Tail_Prone']:
                rotate_angle['rad_y'] = np.pi
            elif subj_pose in ['Foot_Left', 'Tail_Left']:
                rotate_angle['rad_y'] = np.pi
                rotate_angle['rad_z'] = -np.pi/2
            elif subj_pose in ['Foot_Right', 'Tail_Right']:
                rotate_angle['rad_y'] = np.pi
                rotate_angle['rad_z'] = np.pi/2
            else:
                raise NotImplementedError
        return rotate_angle

    @classmethod
    def _correct_orientation(cls, affine, subj_pose, subj_type):
        cls._inspect_subj_info(subj_pose, subj_type)
        rotate_angle = cls._est_rotate_angle(subj_pose)
        affine = helper.rotate_affine(affine, **rotate_angle)
        
        if subj_type != 'Biped':
            affine = helper.rotate_affine(affine, rad_x=-np.pi/2, rad_y=np.pi)
        return affine
    
    @staticmethod
    def _inspect_subj_info(subj_pose, subj_type):
        if subj_pose:
            part, side = subj_pose.split('_')
            assert part in SUBJPOSE['part'], 'Invalid subject position'
            assert side in SUBJPOSE['side'], 'Invalid subject position'
        if subj_type:
            assert subj_type in SUBJTYPE, 'Invalid subject type'


class DataArrayAnalyzer:
    def __init__(self, infoobj: 'ScanInfo', fileobj: BufferedReader|ZipExtFile):
        infoobj = copy(infoobj)
        self._parse_info(infoobj)
        self.buffer = fileobj

    def _parse_info(self, infoobj: 'ScanInfo'):
        if not hasattr(infoobj, 'dataarray'):
            raise AttributeError
        self.slope = infoobj.dataarray['2dseq_slope']
        self.offset = infoobj.dataarray['2dseq_offset']
        self.dtype = infoobj.dataarray['2dseq_dtype']
        self.shape = infoobj.image['shape'][:]
        self.shape_desc = infoobj.image['dim_desc'][:]
        if infoobj.frame_group and infoobj.frame_group['type']:
            self._calc_array_shape(infoobj)
            
    def _calc_array_shape(self, infoobj: 'ScanInfo'):
        self.shape.extend(infoobj.frame_group['shape'][:])
        self.shape_desc.extend([fgid.replace('FG_', '').lower() for fgid in infoobj.frame_group['id']])
    
    def get_dataarray(self):
        self.buffer.seek(0)
        return np.frombuffer(self.buffer.read(), self.dtype).reshape(self.shape, order='F')
