#!/usr/bin/env python3

import argparse
import os
import sys
import tempfile
import brkraw as brk
from typing import Tuple, List, Optional, Any
import sigpy as sp
import nibabel as nib
import numpy as np
from numpy.fft import fftn, ifftn, fftshift, ifftshift
from scipy.signal import get_window
from scipy.interpolate import interp1d
from tqdm import tqdm

# Dependencies brkraw, sigpy, nibabel, numpy, scipy, and tdqm
# tested on Python 3.8, 3.10
# Author: SungHo Lee(shlee@unc.edu)

## Brk-bart
def parse_acqp(rawobj, scan_id):
    # acqp parameter parsing
    acqp = rawobj.get_acqp(scan_id).parameters
    nr = acqp['NR']
    ni = acqp['NI']
    nae = acqp['NAE']  # number of average
    ns = acqp['NSLICES']
    acq_jobs = acqp['ACQ_jobs'][0]
    sz = [acq_jobs[0]/2, acq_jobs[3]/(nr*nae), acq_jobs[-2]]

    wordtype = brk.lib.reference.WORDTYPE[f'_{"".join(acqp["ACQ_word_size"].split("_"))}_SGN_INT']
    byteorder = brk.lib.reference.BYTEORDER[f'{acqp["BYTORDA"]}Endian']

    tr = acqp['ACQ_repetition_time'] / 1000
    dtype_code = np.dtype(f'{byteorder}{wordtype}')
    fid_shape = np.array([2] + sz + [ns]).astype(int).tolist()
    num_frames = int(nr*ni/ns)
    buffer_size = np.prod(fid_shape)*dtype_code.itemsize

    return dict(fid_shape=fid_shape,
                dtype_code=dtype_code,
                num_frames=num_frames,
                buffer_size=buffer_size,
                repetition_time=tr)


def get_traj(rawobj, scan_id):
    method = rawobj.get_method(scan_id).parameters
    traj_shape = np.array(
        [3, method['PVM_Matrix'][0]/2, method['NPro']]).astype(int)
    return np.frombuffer(rawobj._pvobj.get_traj(scan_id), np.double).reshape(traj_shape, order='F')


def calc_trajectory(rawobj, scan_id, params, ext_factors):
    method = rawobj.get_method(scan_id).parameters
    over_samp = method['OverSampling']
    mat_size = np.array(method['PVM_Matrix'])

    num_pts = int((mat_size[0] * over_samp) / 2)
    smp_idx = np.arange(0, int(mat_size[0] / 2))
    smp_idx_oversmp = np.array(
        [c+s for s in smp_idx for c in np.linspace(0, 1-1/over_samp, over_samp)])

    # trajectory
    traj = get_traj(rawobj, scan_id)

    # calculate trajectory oversampling
    # axis2 = number of projection
    traj_oversmp = np.zeros((3, num_pts, params['fid_shape'][2]))
    for i, coord in enumerate(traj):

        step = np.mean(np.diff(coord, 1, axis=0), axis=0)

        coord = np.insert(coord, -1, coord[-1, :], axis=0)
        coord[-1, :] = coord[-2, :] + step
        func = interp1d(np.append(smp_idx, smp_idx[-1]+1), coord, axis=0)

        # Evaluating trajectory at finer intervals
        traj_oversmp[i, :, :] = func(smp_idx_oversmp)

    traj_oversmp[:, :, ::2] = -traj_oversmp[:, :, 1::2]  # correct direction

    traj_oversmp = np.multiply(traj_oversmp, mat_size[:, np.newaxis, np.newaxis]
                               .repeat(traj_oversmp.shape[1], 1)
                               .repeat(traj_oversmp.shape[2], 2))

    proj_order = np.concatenate([np.arange(0, params['fid_shape'][2], 2),
                                 np.arange(1, params['fid_shape'][2], 2)])

    # apply extend FOV factor
    traj_adjusted = traj_oversmp[:, :, proj_order]
    traj_adjusted[0] *= ext_factors[0]
    traj_adjusted[1] *= ext_factors[1]
    traj_adjusted[2] *= ext_factors[2]
    return traj_adjusted


def validate_int_or_list(value):
    if len(value) in {1, 3}:
        return int(value)
    else:
        raise argparse.ArgumentTypeError("Size must be either 1 or 3.")

__version__ = '24.1.01'

def main():
    parser = argparse.ArgumentParser(prog="sordino2nii", description='Reconstruction tool for SORDINO fMRI sequence')
    
    parser.add_argument("-i", "--input", help="input path of raw data", type=str, default=None)
    parser.add_argument("-o", "--prefix", help='output prefix of reconstructed image', type=str, default='output')
    parser.add_argument("-s", "--scanid", help="scan id", type=int, default=None)
    parser.add_argument("-e", "--extention", help="Extension factors for FOV regridding (LR AP SI)", nargs="+", 
                        type=validate_int_or_list, default=[1,1,1])
    parser.add_argument("--offset", help="Index of offset frame (start point of reconstruction)", type=int, default=0)
    parser.add_argument("--num-frames", help='Number of frames to be reconstructed (from offset)', type=int, default=None)
    parser.add_argument("--tmpdir", help="folder to store temporary file", type=str, default=None)
    parser.add_argument("--spoketiming", help="apply spoke timing correction", action='store_true')
    parser.add_argument("--clear-cache", help='delete intermediate binary files generated during reconstruction', action='store_true')
    parser.add_argument("--mem-limit", help='set limit of memory size when loading data (in GB)', type=float, default=0.5)
    
    print(f"++ sordino2nii(v{__version__}): Reconstruction tool for SORDINO fMRI sequence")
    print("++ Authored by: SungHo Lee (email: shlee@unc.edu)")
    
    args = parser.parse_args()
    tqdm_ncols = 100
    # fetch variables
    mem_limit = args.mem_limit
    scan_id = args.scanid
    offset = args.offset
    ext_factor = args.extention * 3 if len(args.extention) == 1 else args.extention
    # gamma = args.gamma[0] if len(args.gamma) == 1 else args.gamma
    prefix = args.prefix
    
    # create temporary folder
    tmpdir = args.tmpdir or os.path.join(os.curdir, '.tmp')
    os.makedirs(tmpdir, exist_ok=True)
    
    # loading data
    try:
        print(f"\n++ Loading input Bruker rawdata {args.input}")
        raw = brk.load(args.input)
        params = parse_acqp(raw, scan_id)
        pvobj = raw._pvobj
        num_frames = args.num_frames or params['num_frames']
    except:
        parser.print_help()
        sys.exit()
    
    # parameters for reconstruction
    print("\n++ Fetch parameters from rawdata")
    num_echos, num_spokes = params['fid_shape'][1:3]
    raw_buffer_size = params['buffer_size']
    raw_dtype = params['dtype_code']
    recon_buffer_offset = offset * raw_buffer_size
    print(f" + Extention factors: x*{ext_factor[0]}, y*{ext_factor[1]}, z*{ext_factor[2]}")
    ext_factor = [ext_factor[1], ext_factor[0], ext_factor[2]]
    ## calculate trajectory
    visu_pars = raw.get_visu_pars(scan_id, 1).parameters
    traj = calc_trajectory(raw, scan_id, params, ext_factor)
    coord = traj.T
    dcf = coord[..., 0] ** 2 + coord[..., 1] ** 2 + coord[..., 2] ** 2
    oshape = (np.array(visu_pars['VisuCoreSize']) * ext_factor).tolist()
    print(f" + Output shape: {oshape[1]}x{oshape[0]}x{oshape[2]}")
    ndim = 4 if num_frames > 1 else 3
    print(f" + Output dim: {ndim}")
    if offset:
        print(f" + Frame offset: {offset}")
    if ndim == 4:
        print(f" + Output num of frames: {num_frames}")
    
    # Image reconstruction
    _caches = []
    with tempfile.NamedTemporaryFile(mode='w+b', delete=False, dir=tmpdir) as recon_f:
        recon_dtype = None
        tr = params['repetition_time']
        scan_time_per_vol = num_spokes * tr
        # Spoke timing correction
        if args.spoketiming:
            print("\n++ Running spoke timing correction for --spoketiming")
            ## Run spoke timing correction
            # parameters for spoke timing correction
            
            target_timing = scan_time_per_vol / 2
            base_timestamps = np.arange(num_frames) * scan_time_per_vol
            target_timestamps = base_timestamps + target_timing
            spoke_buffer_size = int(raw_buffer_size/num_spokes)
            
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False, dir=tmpdir) as stc_f:
                with pvobj._open_object(pvobj._fid[scan_id]) as fid_f:
                    # print the size of file in GB
                    try:
                        file_size = pvobj.filelist[pvobj._fid[scan_id]].file_size / params['num_frames'] * num_frames / 1024**3
                    except:
                        file_size = os.path.getsize(pvobj._fid[scan_id]) / params['num_frames'] * num_frames / 1024**3
                    print(f' + Size: {file_size:.3f} GB')
                
                    # for safety reason, cut data into the size defined at limit_mem_size (in GB)
                    num_segs = np.ceil(file_size / mem_limit).astype(int)
                    print(f' + Split data into {num_segs} segments for saving memory.')
                    
                    num_spokes_per_seg = int(np.ceil(num_spokes / num_segs))
                    if residual_spokes := num_spokes % num_spokes_per_seg:
                        segs = [num_spokes_per_seg for _ in range(num_segs -1)] + [residual_spokes]
                    else:
                        segs = [num_spokes_per_seg for _ in range(num_segs)]

                    spoke_loc = 0
                    stc_dtype = None
                    stc_buffer_size = None
                    for seg_size in tqdm(segs, desc=' - Segments', file=sys.stdout, ncols=tqdm_ncols):
                        # load data
                        spoke_offset = spoke_loc * spoke_buffer_size
                        seg_buffer_size = spoke_buffer_size * seg_size # total buffer size for current segment
                        seg = []
                        for t in range(num_frames):
                            frame_offset = t * raw_buffer_size
                            fid_f.seek(recon_buffer_offset + frame_offset + spoke_offset)
                            seg.append(fid_f.read(seg_buffer_size))
                        seg_data = np.frombuffer(b''.join(seg), dtype=raw_dtype).reshape([2, num_echos, 
                                                                                        seg_size, num_frames], 
                                                                                        order='F')
                        # Spoke timing correction
                        corrected_seg_data = np.empty_like(seg_data)
                        for spoke_id in range(seg_size):
                            cur_spoke = spoke_loc + spoke_id
                            ref_timestamps = base_timestamps + (cur_spoke * tr)
                            for c in range(2): # real and imaginary (complex)
                                for e in range(num_echos):
                                    interp_func = interp1d(ref_timestamps, 
                                                        seg_data[c, e, spoke_id, :], 
                                                        kind='linear',
                                                        fill_value='extrapolate')
                                    corrected_seg_data[c, e, spoke_id, :] = interp_func(target_timestamps)
                        
                        
                        # Store data
                        for t in range(num_frames):
                            frame_offset = t * raw_buffer_size
                            stc_f.seek(frame_offset + spoke_offset)
                            stc_f.write(corrected_seg_data[:,:,:, t].flatten(order='F').tobytes())

                        if not stc_dtype:
                            stc_dtype = corrected_seg_data.dtype
                            stc_buffer_size = np.prod(params['fid_shape']) * stc_dtype.itemsize
                            
                        spoke_loc += seg_size
                    print(' + Success')
                    # clear memory (we only needs stc_f, stc_dtype, stc_buffer_size)
                    ## spoke timing prep related namespaces
                    del tr, target_timing, 
                    del base_timestamps, target_timestamps, spoke_buffer_size
                    ## segmenting related namespaces
                    del file_size, mem_limit, num_segs, 
                    del num_spokes_per_seg, residual_spokes, segs, spoke_loc, 
                    del seg_buffer_size, seg_size, seg_data, num_echos
                    ## spoke timing correction relaated
                    del cur_spoke, spoke_id, ref_timestamps, interp_func
                    del frame_offset, corrected_seg_data
                del fid_f
            
            print("\n++ Reconstruction (FID -> Image[complex])")
            with open(stc_f.name, 'r+b') as fid_f:
                # Reconstruction
                fid_f.seek(0)
                recon_f.seek(0)
                for n in tqdm(range(num_frames), desc=' - Frames', file=sys.stdout, ncols=tqdm_ncols):
                    buffer = fid_f.read(stc_buffer_size)
                    v = np.frombuffer(buffer, dtype=stc_dtype).reshape(params['fid_shape'], order='F')
                    v = (v[0] + 1j*v[1])[np.newaxis, ...]
                    ksp = v.squeeze().T
                    recon_vol = sp.nufft_adjoint(ksp * dcf, coord, oshape=oshape)
                    if n == 0:
                        recon_dtype = recon_vol.dtype
                    recon_f.write(recon_vol.T.flatten(order='C').tobytes())
            _caches.append(stc_f.name)
            print(" + Success")
            
        # Without spoke timing correction
        else:
            print("\n++ Reconstruction (FID -> Image[complex])")
            with pvobj._open_object(pvobj._fid[scan_id]) as fid_f:
                fid_f.seek(recon_buffer_offset)
                recon_f.seek(0)
                for n in tqdm(range(num_frames), desc=' - Frames', file=sys.stdout, ncols=tqdm_ncols):
                    buffer = fid_f.read(raw_buffer_size)
                    v = np.frombuffer(buffer, dtype=raw_dtype).reshape(params['fid_shape'], order='F')
                    v = (v[0] + 1j*v[1])[np.newaxis, ...]
                    ksp = v.squeeze().T
                    recon_vol = sp.nufft_adjoint(ksp * dcf, coord, oshape=oshape)
                    if n == 0:
                        recon_dtype = recon_vol.dtype
                    recon_f.write(recon_vol.T.flatten(order='C').tobytes())
            print(" + Success")
    
    def calc_slope_inter(data):
        inter = np.min(data)
        dmax = np.max(data)
        slope = (dmax - inter) / 2**16

        if data.ndim > 3:
            converted_data = []
            for t in tqdm(range(data.shape[-1]), desc=' - Frame', file=sys.stdout, ncols=tqdm_ncols):
                converted_data.append(((data[..., t] - inter) / slope).round().astype(np.uint16)[..., np.newaxis])
            converted_data = np.concatenate(converted_data, axis=-1)
        else:
            converted_data = ((data - inter) / slope).round().astype(np.uint16)
        return converted_data, slope, inter
    
    # Save to NIFTI file
    with open(recon_f.name, 'r+b') as img_f:
        print(f" + Converting dtype (complex -> float32)...", end='')
        img = np.abs(np.frombuffer(img_f.read(), dtype=recon_dtype).reshape(oshape + [num_frames], order='F'))
        print('success')
        
    
        print(f"\n++ Creating Nifti image")
        output_fpath = f'{prefix}.nii.gz'
        print(f" + convert dtype to UINT16")
        img, slope, inter = calc_slope_inter(img)
        img = img.squeeze()
        print(f" - Slope: {slope:.3f}")
        print(f" - Intercept: {inter:.3f}")
        print(f" - Min: {img.min()}")
        print(f" - Max: {img.max()}")
        method = raw.get_method(scan_id).parameters
        affine = np.array(method['PVM_SpatResol'] + [1])
        position = -1 * np.array(method['PVM_Fov']) * ext_factor / 2
        grad_matrix = np.round(np.array(method['PVM_SPackArrGradOrient'][0]).T, decimals=0).astype(np.int16)
        axis_order = np.arange(img.ndim)
        axis_order[:3] = tuple([int(np.squeeze(np.nonzero(ax))) for ax in grad_matrix])
        flip_axis = np.nonzero(grad_matrix.sum(0) < 0)[0].tolist()
        
        affine[flip_axis] *= -1
        affine = np.diag(affine)
        affine[:3, 3] = position.dot(np.abs(grad_matrix.T))
        
        img = img.transpose(axis_order)
        img = np.flip(img, flip_axis)
        
        # position correction
        print(f"\n + calculating affine matrix")
        axis_order[:3] = [0, 2, 1]
        img = img.transpose(axis_order)
        # img = np.flip(img, 2)
        img = np.flip(img, 1)
        affine[:, [1, 2]] = affine[:, [2, 1]]
        affine[[1, 2], :] = affine[[2, 1], :]
        affine[:, 0] *= -1
        affine[2, 3] *= -1
        # affine[:, 2] *= -1
        print(" - roration:")
        for i in range(3):
            print(f"   {affine[i, 0]}, {affine[i, 1]}, {affine[i, 2]}")
        print(f" - position(LPS): {affine[0,3]:.3f}, {affine[1,3]:.3f}, {affine[2,3]:.3f}")
    
        # save results            
        print(f" - Saving {output_fpath}...", end='')
        niiobj = nib.Nifti1Image(img, affine)
        niiobj.set_qform(affine, 1)
        niiobj.set_sform(affine, 0)
        niiobj.header.set_slope_inter(slope, inter)
        niiobj.header['pixdim'][4] = scan_time_per_vol
        niiobj.to_filename(output_fpath)
        print(f"success")
        
    _caches.append(recon_f.name)
    if args.clear_cache:
        print("\n++ Clear cache for --clear-cache")
        for f in _caches:
            os.remove(f)
    else:
        cache_fpath = f'{prefix}_cache.log'
        print(f"\n++ Saving cache file: {cache_fpath}")
        with open(cache_fpath, 'w+t') as log_f:
            for f in _caches:
                log_f.write(f + '\n')

if __name__ == "__main__":
    main()