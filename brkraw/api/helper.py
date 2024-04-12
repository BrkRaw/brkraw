from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .analyzer import ScanInfoAnalyzer, ScanInfo
import re
import math
import warnings
import contextlib
import numpy as np
from functools import partial, reduce

WORDTYPE = \
    dict(_32BIT_SGN_INT     = 'i',
         _16BIT_SGN_INT     = 'h',
         _8BIT_UNSGN_INT    = 'B',
         _32BIT_FLOAT       = 'f')
BYTEORDER = \
    dict(littleEndian       = '<',
         bigEndian          = '>')

def is_all_element_same(listobj):
    if listobj is None:
        return True
    else:
        return all(map(partial(lambda x, y: x == y, y=listobj[0]), listobj))

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

class BaseHelper:
    def __init__(self):
        self.warns = []
        
    def _warn(self, message):
        warnings.warn(message, UserWarning)
        self.warns.append(message)
        
    
class Protocol(BaseHelper):
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        acqp = analobj.pars.acqp
        method = analobj.pars.method
        visu = analobj.pars.visu
        
        self.pv_version = str(visu['VisuCreatorVersion']) if visu else None
        self.pulse_program = acqp['PULPROG']
        self.scan_name = acqp['ACQ_scan_name']
        self.scan_method = method['Method']
        if visu is None:
            self._warn("visu_pars not found")
            
    def get_info(self):
        return {
            'pv_version': self.pv_version,
            'pulse_program': self.pulse_program,
            'scan_name': self.scan_name,
            'scan_method': self.scan_method,
            'warns': []
        }


class DataArray(BaseHelper):
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        fid_word_type = f'_{"".join(analobj.pars.acqp["ACQ_word_size"].split("_"))}_SGN_INT'
        fid_byte_order = f'{analobj.pars.acqp["BYTORDA"]}Endian'
        self.fid_dtype = np.dtype(f'{BYTEORDER[fid_byte_order]}{WORDTYPE[fid_word_type]}')
        
        byte_order = getattr(analobj, 'visu_core_byte_order')
        word_type = getattr(analobj, 'visu_core_word_type')
        self.data_dtype = np.dtype(f'{BYTEORDER[byte_order]}{WORDTYPE[word_type]}')
        data_slope = getattr(analobj, 'visu_core_data_slope')
        data_offset = getattr(analobj, 'visu_core_data_offs')
        self.data_slope = data_slope[0] \
            if isinstance(data_slope, list) and is_all_element_same(data_slope) else data_slope
        self.data_offset = data_offset[0] \
            if isinstance(data_offset, list) and is_all_element_same(data_offset) else data_offset

    def get_info(self):
        return {
            'fid_dtype': self.fid_dtype,
            '2dseq_dtype': self.data_dtype,
            '2dseq_slope': self.data_slope,
            '2dseq_offset': self.data_offset,
            'warns': self.warns
        }

    
class SlicePack(BaseHelper):
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        fg_info = analobj.info_frame_group if hasattr(analobj, 'info_frame_group') else FrameGroup(analobj).get_info()
        img_info = analobj.info_image if hasattr(analobj, 'info_image') else Image(analobj).get_info()
        if fg_info is None or fg_info['type'] is None:
            num_slice_packs = 1
            num_slices_each_pack = [getattr(analobj, 'visu_core_frame_count')]
            slice_distances_each_pack = [getattr(analobj, 'visu_core_frame_thickness')] \
                if img_info['dim'] > 1 else []
        else:
            if analobj.visu_version == 1:
                parser = self._parse_legacy
            else:
                parser = self._parse_6to360
            
            num_slice_packs, num_slices_each_pack, slice_distances_each_pack = parser(analobj, fg_info)
            if len(slice_distances_each_pack):
                for i, d in enumerate(slice_distances_each_pack):
                    if d == 0:
                        slice_distances_each_pack[i] = getattr(analobj, 'visu_core_frame_thickness')
            if not len(num_slices_each_pack):
                num_slices_each_pack = [1]
    
        self.num_slice_packs = num_slice_packs
        self.num_slices_each_pack = num_slices_each_pack
        self.slice_distances_each_pack = slice_distances_each_pack
        
        disk_slice_order = getattr(analobj, 'visu_core_disk_slice_order') if hasattr(analobj, 'visu_core_disk_slice_order') else 'normal'
        self.is_reverse = 'reverse' in disk_slice_order
        if analobj.visu_version not in (1, 3, 4, 5):
            self._warn(f'Parameters with current Visu Version has not been tested: v{analobj.visu_version}')
                    
    def _parse_legacy(self, analobj, fg_info):
        """
        Parses slice description for legacy cases, PV version < 6.
        This function calculates the number of slice packs, the number of slices in each pack,
        and the slice distances for legacy cases.
        """
        num_slice_packs = 1
        with contextlib.suppress(AttributeError):
            phase_enc_dir = getattr(analobj, 'visu_acq_image_phase_enc_dir')
            phase_enc_dir = [phase_enc_dir[0]] if is_all_element_same(phase_enc_dir) else phase_enc_dir
            num_slice_packs = len(phase_enc_dir)

        shape = fg_info['shape']
        num_slices_each_pack = []
        with contextlib.suppress(ValueError):
            slice_fid = fg_info['id'].index('FG_SLICE')
            if num_slice_packs > 1:
                num_slices_each_pack = [int(shape[slice_fid]/num_slice_packs) for _ in range(num_slice_packs)]
            else:
                num_slices_each_pack = [shape[slice_fid]]

        slice_fg = [fg for fg in fg_info['id'] if 'slice' in fg.lower()]
        if len(slice_fg):
            if num_slice_packs > 1:
                num_slices_each_pack.extend(
                    int(shape[0] / num_slice_packs)
                    for _ in range(num_slice_packs)
                )
            else:
                num_slices_each_pack.append(shape[0])
        slice_distances_each_pack = [getattr(analobj, 'visu_core_frame_thickness') for _ in range(num_slice_packs)]
        return num_slice_packs, num_slices_each_pack, slice_distances_each_pack
    
    def _parse_6to360(self, analobj, fg_info):
        """
        Parses slice description for cases with PV version 6 to 360 slices.
        This function calculates the number of slice packs, the number of slices in each pack,
        and the slice distances for cases with 6 to 360 slices.
        """
        if hasattr(analobj, 'visu_core_slice_packs_def'):
            num_slice_packs = getattr(analobj, 'visu_core_slice_packs_def')[0][1]
        else:
            num_slice_packs = 1
        slices_desc_in_pack = getattr(analobj, 'visu_core_slice_packs_slices') \
            if hasattr(analobj, 'visu_core_slice_packs_slices') else []
        slice_distance = getattr(analobj, 'visu_core_slice_packs_slice_dist') \
            if hasattr(analobj, 'visu_core_slice_packs_slice_dist') else []
            
        slice_fg = [fg for fg in fg_info['id'] if 'slice' in fg.lower()]
        if len(slice_fg):
            if len(slices_desc_in_pack):
                num_slices_each_pack = [slices_desc_in_pack[0][1] for _ in range(num_slice_packs)]
            else:
                num_slices_each_pack = [1]
            if isinstance(slice_distance, list):
                slice_distances_each_pack = [slice_distance[0] for _ in range(num_slice_packs)]
            elif isinstance(slice_distance, (int, float)):
                slice_distances_each_pack = [slice_distance for _ in range(num_slice_packs)]
            else:
                self._warn("Not supported data type for Slice Distance")
        else:
            num_slices_each_pack = [1]
            slice_distances_each_pack = [getattr(analobj, 'visu_core_frame_thickness')]
        return num_slice_packs, num_slices_each_pack, slice_distances_each_pack

    def get_info(self):
        return {
            'num_slice_packs': self.num_slice_packs,
            'num_slices_each_pack': self.num_slices_each_pack,
            'slice_distances_each_pack': self.slice_distances_each_pack,
            'slice_distance_unit': 'mm',
            'reverse_slice_order': self.is_reverse,
            'warns': self.warns
        }       


class FrameGroup(BaseHelper):
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        if hasattr(analobj, 'visu_fg_order_desc_dim'):
            self.exists = True
            self.type = getattr(analobj, 'visu_core_frame_type') \
                if hasattr(analobj, 'visu_core_frame_type') else None
            self.shape = []
            self.id = []
            self.comment = []
            self.dependent_vals = []
            for (shape, fgid, comment, vals_start, vals_cnt) in getattr(analobj, 'visu_fg_order_desc'):
                self.shape.append(shape)
                self.id.append(fgid)
                self.comment.append(comment)
                self.dependent_vals.append([
                    getattr(analobj, 'visu_group_dep_vals')[vals_start + count]
                        for count in range(vals_cnt)
                    ] if vals_cnt else [])
            self.size = reduce(lambda x, y: x * y, self.shape)
        else:
            self.exists = False
            self._warn('frame group information')
            
    def get_info(self):
        if not self.exists:
            return None
        return {
            'type': self.type,
            'size': self.size,
            'shape': self.shape,
            'id': self.id,
            'comment': self.comment,
            'dependent_vals': self.dependent_vals,
            'warns': self.warns
            }


class Cycle(BaseHelper):
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        scan_time = getattr(analobj, 'visu_acq_scan_time') or 0
        fg_info = analobj.info_frame_group if hasattr(analobj, 'info_frame_group') else FrameGroup(analobj).get_info()
        fg_not_slice = []
        if fg_info != None and fg_info['type'] != None:
            fg_not_slice.extend([fg_info['shape'][id] for id, fg in enumerate(fg_info['id'])
                            if not re.search('slice', fg, re.IGNORECASE)])
        self.num_frames = np.prod(fg_not_slice) if len(fg_not_slice) else 1
        self.time_step = (scan_time / self.num_frames)
    
    def get_info(self):
        return {
            "num_frames": self.num_frames,
            "time_step": self.time_step,
            "unit": 'msec',
            'warns': self.warns
            }
        

class Image(BaseHelper):
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        self.dim = getattr(analobj, 'visu_core_dim')
        self.dim_desc = getattr(analobj, 'visu_core_dim_desc')
        fov = getattr(analobj, 'visu_core_extent') if hasattr(analobj, 'visu_core_extent') else None
        shape = getattr(analobj, 'visu_core_size') if hasattr(analobj, 'visu_core_size') else None
        self.resolusion = np.divide(fov, shape).tolist() if (fov and shape) else None
        self.field_of_view = fov
        self.shape = shape
        
        if self.dim > 3:
            self._warn('Image dimension larger than 3')
        message = lambda x: f'image contains {x} dimension'
        if isinstance(self.dim_desc, list):
            for d in self.dim_desc:
                if d != 'spatial':
                    self._warn(message(d))
        elif isinstance(self.dim_desc, str):
            if self.dim_desc != 'spatial':
                self._warn(message(self.dim_desc)) 
    
    def get_info(self):
        return {
            'dim': self.dim,
            'dim_desc': self.dim_desc,
            'shape': self.shape,
            'resolution': self.resolusion,
            'field_of_view': self.field_of_view,
            'unit': 'mm',
            'warns': self.warns
        }
    
        
class Orientation(BaseHelper):
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        info_slicepack = analobj.info_slicepack if hasattr(analobj, 'info_slicepack') else SlicePack(analobj).get_info()
        self.subject_type = getattr(analobj, 'visu_subject_type') \
            if hasattr(analobj, 'visu_subject_type') else None
        self.subject_position = getattr(analobj, 'visu_subject_position') \
            if hasattr(analobj, 'visu_subject_position') else None
        self._orient = getattr(analobj, 'visu_core_orientation').tolist()
        self._position = getattr(analobj, 'visu_core_position')
        self.gradient_orient = getattr(analobj, 'pvm_s_pack_arr_grad_orient')
        self.num_slice_packs = info_slicepack['num_slice_packs']
        self.gradient_encoding_dir = self._get_gradient_encoding_dir(analobj)
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
            'gradient_orient': self.gradient_orient
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
    def _get_gradient_encoding_dir(cls, analobj: 'ScanInfoAnalyzer'):
        if analobj.visu_version != 1:
            return getattr(analobj, 'visu_acq_grad_encoding')
        phase_enc = getattr(analobj, 'visu_acq_image_phase_enc_dir')
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
