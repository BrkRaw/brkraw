import math
from copy import copy as cp

import numpy as np
from nibabel.affines import from_matvec, to_matvec

from .reference import ERROR_MESSAGES


def build_affine_from_orient_info(resol, rmat, pose,
                                  subj_pose, subj_type, slice_orient):
    if slice_orient in ['axial', 'sagital']:
        resol = np.diag(np.array(resol))
    else:
        resol = np.diag(np.array(resol) * np.array([1, 1, -1]))
    rmat = rmat.T.dot(resol)

    affine = from_matvec(rmat, pose)

    # convert space from image to subject
    # below positions are all reflect human-based position
    if subj_pose:
        if subj_pose == 'Head_Supine':
            affine = apply_rotate(affine, rad_z=np.pi)
        elif subj_pose == 'Head_Prone':
            pass
        # From here, not urgent, extra work to determine correction matrix needed.
        elif subj_pose == 'Head_Left':
            affine = apply_rotate(affine, rad_z=np.pi/2)
        elif subj_pose == 'Head_Right':
            affine = apply_rotate(affine, rad_z=-np.pi/2)
        elif subj_pose in ['Foot_Supine', 'Tail_Supine']:
            affine = apply_rotate(affine, rad_x=np.pi)
        elif subj_pose in ['Foot_Prone', 'Tail_Prone']:
            affine = apply_rotate(affine, rad_y=np.pi)
        elif subj_pose in ['Foot_Left', 'Tail_Left']:
            affine = apply_rotate(affine, rad_z=np.pi/2)
        elif subj_pose in ['Foot_Right', 'Tail_Right']:
            affine = apply_rotate(affine, rad_z=-np.pi/2)
        else:  # in case Bruker put additional value for this header
            raise Exception(ERROR_MESSAGES['NotIntegrated'])

    if subj_type != 'Biped':
        # correct subject space if not biped (human or non-human primates)
        # not sure this rotation is independent with subject pose, so put here instead last
        affine = apply_rotate(affine, rad_x=-np.pi/2, rad_y=np.pi)
    return affine


def reversed_pose_correction(pose, rmat, distance):
    reversed_pose = rmat.dot(pose)
    reversed_pose[-1] += distance
    corrected_pose = rmat.T.dot(reversed_pose)
    return corrected_pose


def is_rotation_matrix(matrix):
    t_matrix = np.transpose(matrix)
    should_be_identity = np.dot(t_matrix, matrix)
    i = np.identity(3, dtype=matrix.dtype)
    n = np.linalg.norm(i - should_be_identity)
    return n < 1e-6


def apply_flip(matrix, axis, mat=True, vec=True):
    '''axis = x or y or z'''
    flip_idx = dict(x=0, y=1, z=2)
    orig_mat, orig_vec = to_matvec(matrix)

    aff_mat = np.ones(3)
    aff_mat[flip_idx[axis]] = -1
    aff_mat = np.diag(aff_mat)
    if mat:
        flip_mat = aff_mat.dot(orig_mat)
    else:
        flip_mat = orig_mat
    if vec:
        flip_vec = aff_mat.dot(orig_vec)
    else:
        flip_vec = orig_vec
    return from_matvec(flip_mat, flip_vec)


def calc_eulerangle(matrix):
    assert (is_rotation_matrix(matrix))

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


def apply_rotate(matrix, rad_x=0, rad_y=0, rad_z=0):
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
    af_mat, af_vec = to_matvec(matrix)
    rotated_mat = rmat['z'].dot(rmat['y'].dot(rmat['x'].dot(af_mat)))
    rotated_vec = rmat['z'].dot(rmat['y'].dot(rmat['x'].dot(af_vec)))
    return from_matvec(rotated_mat, rotated_vec)


def apply_affine(matrix, affine):
    return affine.dot(matrix)


def swap_orient_matrix(orient_matrix, axis_orient):

    orient_matrix = cp(orient_matrix)

    axis_for_swap = []
    for origin, destination in enumerate(axis_orient):
        if origin != destination:
            axis_for_swap.append(destination)
    orient_matrix.T[axis_for_swap] = orient_matrix.T[axis_for_swap[::-1]]
    return orient_matrix


def get_origin(slice_position, gradient_orient):
    """ TODO: the case was not fully tested, if any coordinate mismatch happened, this function will be the issue.
    Args:
        slice_position:  visu_pars.parameters['VisuCorePosition']
        gradient_orient: method.parameters['PVM_SPackArrGradOrient']

    Returns:
        x, y, z coordinate for origin of image matrix
    """
    slice_position = cp(slice_position)
    dx, dy, dz = map(lambda x: x.max() - x.min(), slice_position.T)
    max_delta_axis = np.argmax([dx, dy, dz])
    rx, ry, rz = [None, None, None]

    if gradient_orient != None:
        zmat = np.zeros(gradient_orient[0].shape)
        for cid, col in enumerate(gradient_orient[0].T):
            yid = np.argmax(abs(col))
            zmat[cid, yid] = np.round(col[yid], decimals=0)
        rx, ry, rz = calc_eulerangle(np.round(zmat.T))

    if max_delta_axis == 0:     # sagital
        if rx != None: # PV 5 filter, only PV6 has gradient_orient info
            if rz == 90: # typical case
                idx = slice_position.T[max_delta_axis].argmin()
            else:
                idx = slice_position.T[max_delta_axis].argmax()
        else:
            idx = slice_position.T[max_delta_axis].argmax()
    elif max_delta_axis == 1:   # coronal
        if rx != None:
            if rx == -90:    # FOV flipped
                if ry == -90:   # Cyceron cases # 5 and 9
                    idx = slice_position.T[max_delta_axis].argmax()
                else:
                    idx = slice_position.T[max_delta_axis].argmin()
            else: # rx == -90 are the typical case
                idx = slice_position.T[max_delta_axis].argmax()
        else:
            idx = slice_position.T[max_delta_axis].argmaxs()
    elif max_delta_axis == 2:   # axial
        if rx != None:
            if (abs(ry) == 180) or ((abs(rx) == 180) and (abs(rz) == 180)):
                # typical case
                idx = slice_position.T[max_delta_axis].argmax()
            else:
                idx = slice_position.T[max_delta_axis].argmin()
        else:
            idx = slice_position.T[max_delta_axis].argmin()
    else:
        raise Exception
    origin = slice_position[idx]
    return origin


def reverse_swap(swap_code):
    reversed_code = [0, 0, 0]
    for target, origin in enumerate(swap_code):
        reversed_code[origin] = target
    return reversed_code
