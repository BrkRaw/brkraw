from __future__ import annotations
import math
import numpy as np
from typing import TYPE_CHECKING
from .base import BaseHelper, is_all_element_same
from .slicepack import SlicePack
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer


def from_matvec(mat, vec):
    """Create an affine transformation matrix from a matrix and a vector."""
    if mat.shape == (3, 3) and vec.shape == (3,):
        affine = np.eye(4)
        affine[:3, :3] = mat
        affine[:3, 3] = vec
        return affine
    else:
        raise ValueError("Matrix must be 3x3 and vector must be 1x3")

def to_matvec(affine):
    """
    Decompose a 4x4 affine matrix into a 3x3 matrix and a 1x3 vector.

    Parameters:
    affine (numpy.ndarray): A 4x4 affine transformation matrix.

    Returns:
    tuple: A 3x3 matrix and a 1x3 vector.
    """
    if affine.shape != (4, 4):
        raise ValueError("Affine matrix must be 4x4")
    mat = affine[:3, :3]
    vec = affine[:3, 3]
    return mat, vec

def rotate_affine(affine, rad_x=0, rad_y=0, rad_z=0):
    ''' axis = x or y or z '''
    rmat = dict(x = np.array([[1, 0, 0],
                            [0, np.cos(rad_x), -np.sin(rad_x)],
                            [0, np.sin(rad_x), np.cos(rad_x)]]).astype('float'),
                y = np.array([[np.cos(rad_y), 0, np.sin(rad_y)],
                            [0, 1, 0],
                            [-np.sin(rad_y), 0, np.cos(rad_y)]]).astype('float'),
                z = np.array([[np.cos(rad_z), -np.sin(rad_z), 0],
                            [np.sin(rad_z), np.cos(rad_z), 0],
                            [0, 0, 1]]).astype('float'))
    af_mat, af_vec = to_matvec(affine)
    rotated_mat = rmat['z'].dot(rmat['y'].dot(rmat['x'].dot(af_mat)))
    rotated_vec = rmat['z'].dot(rmat['y'].dot(rmat['x'].dot(af_vec)))
    return from_matvec(rotated_mat, rotated_vec)


class Orientation(BaseHelper):
    """
    Dependencies:
        SlicePack
        method
        visu_pars

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        visu_pars = analobj.visu_pars
        info_slicepack = analobj.get("info_slicepack") or SlicePack(analobj).get_info()
        self.subject_type = visu_pars.get("VisuSubjectType")
        self.subject_position = visu_pars.get("VisuSubjectPosition")
        self._orient = visu_pars["VisuCoreOrientation"].tolist()
        self._position = visu_pars["VisuCorePosition"]
        self.gradient_orient = analobj.method["PVM_SPackArrGradOrient"]
        self.num_slice_packs = info_slicepack['num_slice_packs']
        self.gradient_encoding_dir = self._get_gradient_encoding_dir(visu_pars)
        self.orientation = []
        self.orientation_desc = []
        self.volume_origin = []
    
        if self.num_slice_packs > 1:
            self._case_multi_slicepacks()
        else:
            self._case_single_slicepack()
    
    def get_info(self):
        return {
            'subject_type': self.subject_type,
            'subject_position': self.subject_position,
            'volume_origin': self.volume_origin,
            'orientation': self.orientation,
            'orientation_desc': self.orientation_desc,
            'gradient_orient': self.gradient_orient,
            'warns': self.warns
        }
    
    def _case_multi_slicepacks(self):
        if len(self._orient) != self.num_slice_packs:
            self._case_multi_slicepacks_multi_slices()
            self.is_msp_ms = True
        else:
            self.is_msp_ms = False

        for id, ori in enumerate(self._orient):
            rs_ori = np.array(ori).reshape((3,3))
            self.orientation.append(rs_ori)
            self.orientation_desc.append(self._get_orient_axis(rs_ori))
            if self.is_msp_ms:
                self.volume_origin.append(self._est_volume_origin(id))
            else:
                self.volume_origin.append(self._position[id])
            
    def _case_single_slicepack(self):
        if is_all_element_same(self._orient):
            self.orientation = np.array(self._orient[0]).reshape((3,3))
            self.orientation_desc = self._get_orient_axis(self.orientation)
            self.volume_origin = self._est_volume_origin()
        else:
            raise NotImplementedError
    
    def _case_multi_slicepacks_multi_slices(self):
        if not self.num_slice_packs % len(self._orient):
            raise NotImplementedError
        start = 0
        num_slices = int(len(self._orient) / self.num_slice_packs)
        orientation = []
        positions = []
        for _ in range(self.num_slice_packs):
            ori_stack = self._orient[start:start + num_slices]
            pos_stack = self._position[start:start + num_slices]
            if is_all_element_same(ori_stack):
                orientation.append(ori_stack[0])
                positions.append(pos_stack)
            start += num_slices
        self._orient = orientation
        self._position = positions
    
    def _est_volume_origin(self, id: int|None =None):
        """Estimate the origin coordinates of the Volume matrix.

        Notes:
            This code has been tested on a limited dataset and may generate mis-estimations.

        Returns:
            list: x, y, z coordinates of the volume origin
        """
        position = self._position[0] if isinstance(self._position, list) else self._position
        position = position[id] if id != None else position
        
        dx, dy, dz = map(lambda x: x.max() - x.min(), position.T)
        max_diff_axis = np.argmax([dx, dy, dz])

        if not isinstance(self.gradient_orient, np.ndarray):
            return self._est_origin_legacy(position, max_diff_axis)
        zmat = np.zeros(self.gradient_orient[0].shape)
        for cid, col in enumerate(self.gradient_orient[0].T):
            yid = np.argmax(abs(col))
            zmat[cid, yid] = np.round(col[yid], decimals=0)
        rx, ry, rz = self._calc_eulerangle(np.round(zmat.T))
        return self._est_origin_pv6to360(position, max_diff_axis, rx, ry, rz)
    
    @staticmethod
    def _est_origin_legacy(position, max_diff_axis):
        """sub-method to estimate origin coordinate from PV version < 6

        Args:
            max_diff_axis (int): The index of the maximum difference axis.

        Returns:
            numpy.ndarray: The origin coordinate based on the maximum difference axis.
        """
        if max_diff_axis in [0, 1]:
            idx = position.T[max_diff_axis].argmax()
        elif max_diff_axis == 2:
            idx = position.T[max_diff_axis].argmin()
        else:
            raise NotImplementedError
        return position[idx]
    
    @staticmethod
    def _est_origin_pv6to360(position, max_diff_axis, rx, ry, rz):
        """sub-method to estimate origin coordinate from PV version >= 6

        Args:
            max_diff_axis (int): The index of the maximum difference axis.
            rx: calculated eulerangle of x axis of gradient
            ry: calculated eulerangle of y axis of gradient
            rz: calculated eulerangle of z axis of gradient

        Returns:
            numpy.ndarray: The origin coordinate based on the maximum difference axis.
        """
        max_axis = position.T[max_diff_axis]
        if max_diff_axis == 0:
            idx = max_axis.argmin() if rx == 90 else max_axis.argmax()
        elif max_diff_axis == 1:
            if rx == -90 and ry == -90 or rx != -90:
                idx = max_axis.argmax()
            else:
                idx = max_axis.argmin()
        elif max_diff_axis == 2:
            if (abs(ry) == 180) or ((abs(rx) == 180) and (abs(rz) == 180)):
                idx = max_axis.argmax()
            else:
                idx = max_axis.argmin()
        else:
            raise NotImplementedError
        return position[idx]
    
    @staticmethod
    def _get_orient_axis(orient_matrix):
        return [np.argmax(abs(orient_matrix[:, 0])),
                np.argmax(abs(orient_matrix[:, 1])),
                np.argmax(abs(orient_matrix[:, 2]))]
        
    @staticmethod
    def _is_rotation_matrix(matrix):
        t_matrix = np.transpose(matrix)
        should_be_identity = np.dot(t_matrix, matrix)
        i = np.identity(3, dtype=matrix.dtype)
        n = np.linalg.norm(i - should_be_identity)
        return n < 1e-6
    
    @staticmethod
    def _calc_eulerangle(matrix):
        assert (Orientation._is_rotation_matrix(matrix))

        sy = math.sqrt(matrix[0, 0] * matrix[0, 0] + matrix[1, 0] * matrix[1, 0])
        singular = sy < 1e-6
        if not singular:
            x = math.atan2(matrix[2, 1], matrix[2, 2])
            y = math.atan2(-matrix[2, 0], sy)
            z = math.atan2(matrix[1, 0], matrix[0, 0])
        else:
            x = math.atan2(-matrix[1, 2], matrix[1, 1])
            y = math.atan2(-matrix[2, 0], sy)
            z = 0
        return np.array([math.degrees(x),
                         math.degrees(y),
                         math.degrees(z)])
    
    @classmethod
    def _get_gradient_encoding_dir(cls, visu_pars):
        if visu_pars["VisuVersion"] != 1:
            return visu_pars["VisuAcqGradEncoding"]
        phase_enc = visu_pars["VisuAcqImagePhaseEncDir"]
        phase_enc = phase_enc[0] if is_all_element_same(phase_enc) else phase_enc
        return (
            [cls._decode_encdir(p) for p in phase_enc] \
                if isinstance(phase_enc, list) and len(phase_enc) > 1 \
                else cls._decode_encdir(phase_enc)
        )
    
    @staticmethod
    def _decode_encdir(enc_param):
        if enc_param == 'col_dir':
            return ['read_enc', 'phase_enc']
        elif enc_param == 'row_dir':
            return ['phase_enc', 'read_enc']
        elif enc_param == 'col_slice_dir':
            return ['read_enc', 'phase_enc', 'slice_enc']
        elif enc_param == 'row_slice_dir':
            return ['phase_enc', 'read_enc', 'slice_enc']
        else:
            raise NotImplementedError
