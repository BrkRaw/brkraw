from __future__ import annotations
from brkraw.api import helper
from .base import BaseAnalyzer
import numpy as np
from copy import copy
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..brkobj import ScanInfo


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


class AffineAnalyzer(BaseAnalyzer):
    def __init__(self, infoobj: 'ScanInfo'):
        infoobj = copy(infoobj)
        if infoobj.image['dim'] == 2:
            xr, yr = infoobj.image['resolution']
            self.resolution = [(xr, yr, zr) for zr in infoobj.slicepack['slice_distances_each_pack']]
        elif infoobj.image['dim'] == 3:
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
