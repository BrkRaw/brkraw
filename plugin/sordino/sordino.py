from __future__ import annotations
import os
import sys
import warnings
import tempfile
import numpy as np
import sigpy as sp
from pathlib import Path
from tqdm import tqdm
from scipy.interpolate import interp1d
from brkraw.app.tonifti import BasePlugin
from brkraw.app.tonifti.base import ScaleMode
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from nibabel.nifti1 import Nifti1Header
    from typing import List, Union, Optional, Tuple
    from brkraw.app.tonifti import PvScan, PvFiles
    from io import BufferedReader, BufferedWriter
    from zipfile import ZipExtFile

class Sordino(BasePlugin):
    """ SORDINO: Plugin to Convert Bruker's SORDINO Images to NifTi File for ToNifti App in Brkraw
    ParaVision Compatability: > 360.x
    """
    _recon_dtype: Optional[np.dtype] = None
    
    def __init__(self, pvobj: Union['PvScan', 'PvFiles'],
                 ext_factors: List[float, float, float]=None, 
                 offset: Optional[int]=None, 
                 num_frames: Optional[int]=None,
                 spoketiming: Optional[bool]=False,
                 mem_limit: Optional[float]=None,
                 tmpdir: Optional[Path]=None,
                 nufft: Optional[str]='sigpy',
                 scale_mode: Optional[ScaleMode]=None,
                 **kwargs
                 ) -> None:
        super().__init__(pvobj, **kwargs)
        self._inspect()
        self._set_params()
        self._set_cache(tmpdir)
        self.ext_factors: List[float, float, float] = ext_factors or [1,1,1]
        self.offset: int = offset or 0
        self.spoketiming: bool = spoketiming
        self.mem_limit: Optional[float] = mem_limit
        self.num_frames: Optional[int] = num_frames or self._num_frames
        self.nufft: str = nufft
        self.scale_mode: ScaleMode = scale_mode or ScaleMode.HEADER
        self.slope, self.inter = 1, 0
        
    def get_dataobj(self) -> np.ndarray:
        self._set_trajectory()
        if self.spoketiming and self.num_frames > 1:
            bufferobj, buffer_size = self._fid_correct_spoketiming()
            dataobj = self._recon_fid(bufferobj, buffer_size)
        else:
            dataobj = self._recon_fid()
        dataobj = np.abs(dataobj) # magnitude image only
        dataobj = self._dataobj_correct_orientation(dataobj)
        if self.scale_mode == ScaleMode.HEADER:
            self._calc_slope_inter(dataobj)
            dataobj = self._dataobj_rescale_to_uint16(dataobj)
        return dataobj
    
    def get_affine(self, reco_id:Optional[int]=None, 
                   subj_type:Optional[str]=None, 
                   subj_position:Optional[str]=None) -> np.ndarray:
        return super().get_affine(self, reco_id=reco_id, 
                                  subj_type=subj_type, 
                                  subj_position=subj_position)
    
    def get_nifti1header(self) -> Nifti1Header:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            header = super().get_nifti1header(self)
            if self.scale_mode == ScaleMode.HEADER:
                header.set_slope_inter(*self._calc_slope_inter())
            return header
    
    def _calc_slope_inter(self, dataobj: np.ndarray):
        dmax = np.max(dataobj)
        self.inter = np.min(dataobj)
        self.slope = (dmax - self.inter) / 2**16
        
    def _dataobj_rescale_to_uint16(self, dataobj: np.ndarray) -> np.ndarray:
        if self.verbose:
            print(f" + convert dtype to UINT16")
            print(f"   - Slope: {self.slope:.3f}")
            print(f"   - Intercept: {self.inter:.3f}")
        if dataobj.ndim > 3:
            converted_dataobj = []
            for t in tqdm(range(dataobj.shape[-1]), desc=' - Frame', file=sys.stdout, ncols=80):
                converted_dataobj.append(((dataobj[..., t] - self.inter) / self.slope).round().astype(np.uint16)[..., np.newaxis])
            converted_dataobj = np.concatenate(converted_dataobj, axis=-1)
        else:
            converted_dataobj = ((dataobj - self.inter) / self.slope).round().astype(np.uint16)
        return converted_dataobj
    
    def _set_cache(self, tmpdir: Optional[Path]) -> None:
        self.tmpdir: Path = tmpdir or Path.home() / '.tmp'
        self.tmpdir.mkdir(exist_ok=True)
    
    def _inspect(self) -> None:
        """
        Inspect the provided pvobj to ensure it is compatible with this plugin.

        Args:
            pvobj (object): The object to be validated for compatibility.

        Raises:
            NotImplementedError: If the pvobj's type or attributes do not meet the plugin's requirements.

        This method checks for the necessary attributes in the pvobj required for SORDINO reconstruction.
        It also validates that the pvobj is not an instance of 'PvReco', as support for this type is not implemented.
        """
        if self.verbose:
            print("++ Inspecting compatibility of imported pvobj for SORDINO reconstruction...")
        if self.pvobj.isinstance('PvReco'):
            raise NotImplementedError("Support for 'PvReco' is not implemented.")
        required_fields = ['method', 'acqp', 'traj', 'rawdata.job0']
        missing_fields = [field for field in required_fields if not hasattr(self.pvobj, field)]
        if missing_fields:
            error_message = f"Input pvobj is missing required fields: {', '.join(missing_fields)}"
            raise NotImplementedError(error_message)
        if not hasattr(self.info, 'orientation'):
            warnings.warn("Input object is missing the 'orientation' attribute. This is not critical, but the orientation of the reconstructed image might be incorrect.", UserWarning)

    def _get_fid(self) -> Union[BufferedReader, ZipExtFile]:
        return self.pvobj.get_fid()
        
    def _get_traj(self) -> Union[BufferedReader, ZipExtFile]:
        return self.pvobj['traj']
    
    def _set_params(self) -> None:
        # acqp params
        if self.verbose:
            print("\n++ Fetch parameters from PvObj...")
        acqp = self.pvobj.acqp
        nr = acqp['NR']
        ni = acqp['NI']
        nae = acqp['NAE']
        ns = acqp['NSLICES']
        acq_jobs = acqp['ACQ_jobs'][0]
        
        self.repetition_time = acqp['ACQ_repetition_time'] / 1000
        self.fid_shape = np.array([2, acq_jobs[0]/2, acq_jobs[3]/(nr*nae), acq_jobs[-2], ns]).astype(int).tolist()
        self._num_frames = int(nr * ni / ns)
        self.dtype_code = self.info.fid['dtype']
        self.buffer_size = np.prod(self.fid_shape) * self.dtype_code.itemsize
        
        # method
        method = self.pvobj.method
        npro = method['NPro']
        mat_size = method['PVM_Matrix']
        over_samp = method['OverSampling']
        
        self.mat_size = np.array(mat_size)
        self.num_pts = int((mat_size[0] * over_samp) / 2)
        self.smp_idx = np.arange(0, int(mat_size[2] / 2))
        self.smp_idx_oversmp = np.array([c + s for s in self.smp_idx \
            for c in np.linspace(0, 1 - 1 / over_samp, over_samp)])
        self.traj_shape = np.array([3, mat_size[0]/2, npro]).astype(int)

    def _set_trajectory(self) -> None:
        with self._get_traj() as f:
            self.traj = np.frombuffer(f.read(), np.double).reshape(self.traj_shape, order='F')
            self._traj_apply_oversampling()
            self._traj_correct_readout_direction()
            self._traj_correct_projection_order()
            if all(np.array(self.ext_factors) != 1):
                if self.verbose:
                    ef = map('*'.join, list(zip(['x', 'y', 'z'], map(str, self.ext_factors))))
                    print(f" + Extention factors: {', '.join(list(ef))}")
                self._traj_apply_extension_factors()

    def _traj_apply_oversampling(self) -> None:
        traj = np.zeros((3, self.num_pts, self.fid_shape[2]))
        for i, coord in enumerate(self.traj):
            step = np.mean(np.diff(coord, 1, axis=0), axis=0)
            coord = np.insert(coord, -1, coord[-1, :], axis=0)
            coord[-1, :] = coord[-2, :] + step
            func = interp1d(np.append(self.smp_idx, self.smp_idx[-1]+1), coord, axis=0)
            # Evaluating trajectory at finer intervals
            traj[i, :, :] = func(self.smp_idx_oversmp)
        self.traj = traj

    def _traj_correct_readout_direction(self) -> None:
        self.traj[:, :, ::2] = -self.traj[:, :, 1::2]
        self.traj = np.multiply(self.traj, self.mat_size[:, np.newaxis, np.newaxis]
                                .repeat(self.traj.shape[1], 1)
                                .repeat(self.traj.shape[2], 2))
    
    def _traj_correct_projection_order(self) -> None:
        proj_order = np.concatenate([np.arange(0, self.fid_shape[2], 2),
                                     np.arange(1, self.fid_shape[2], 2)])
        self.traj = self.traj[:, :, proj_order]

    def _traj_apply_extension_factors(self):
        for i, ef in self.ext_factors:
            self.traj[i] *= ef
    
    def _dataobj_correct_orientation(self, dataobj) -> None:
        """Correct the subject orientation to match that of the online reconstructed image.
        Note: This is experimental and has only been tested on a small number of cases.
        Subject to updates and revisions."""
        # logical to physical orientation correction
        grad_mat = self.pvobj.acqp['ACQ_GradientMatrix'][0]
        corrected_dataobj = self._rotate_dataobj(dataobj, grad_mat)
        if hasattr(self.info, 'orientation'):
            visu_ori = self.info.orientation['orientation']
            corrected_dataobj = self._rotate_dataobj(corrected_dataobj, visu_ori)
        return corrected_dataobj
            
    @staticmethod
    def _rotate_dataobj(dataobj: np.ndarray, rotation_matrix) -> np.ndarray:
        axis_order = np.nonzero(rotation_matrix.T)[1].tolist()
        if len(dataobj.shape) > 3:
            axis_order += [3]
        corrected_dataobj = np.transpose(dataobj, axis_order)
        x, y, z = rotation_matrix.sum(0)
        return corrected_dataobj[::x, ::y, ::z, ...]
    
    def _recon_fid(self, filepath=None, buffer_size=None) -> np.ndarray:
        buffer_size = buffer_size or self.buffer_size
        output_shape = np.round(self.mat_size * self.ext_factors, decimals=0).tolist()
        buffer_offset = 0 if filepath else self.offset * buffer_size
        if self.verbose:
            print("\n++ Reconstruction (FID -> Image[complex])")
            print(f" + Output shape: {'x'.join(map(str, output_shape))}")
            ndim = 4 if self.num_frames > 1 else 3
            print(f" + Output dim: {ndim}")
            if self.offset:
                print(f" + Frame offset: {self.offset}")
            if ndim == 4:
                print(f" + Output num of frames: {self.num_frames}")
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, dir=self.tmpdir) as f_recon:
            if filepath:
                with open(filepath, 'rb') as f_fid:
                    self._recon_process(f_fid, f_recon, buffer_offset, output_shape)
            else:
                with self._get_fid() as f_fid:
                    self._recon_process(f_fid, f_recon, buffer_offset, output_shape)
            if self.verbose:
                print(f" + Converting dtype (complex -> float32)...", end='')
            shape = output_shape + [self.num_frames] if self.num_frames > 1 else output_shape
            f_recon.seek(0)
            recon = np.frombuffer(f_recon.read(), dtype=self._recon_dtype).reshape(shape, order='F')
            if self.verbose:
                print('Success')
        self._buffers.append(f_recon)
        return recon
    
    def _recon_process(self, 
                       fid_buffer: Union['BufferedReader', 'ZipExtFile'], 
                       recon_buffer: 'BufferedWriter', 
                       buffer_offset: int, 
                       output_shape: list) -> None:
        fid_buffer.seek(buffer_offset)
        if self.verbose:
            framerange = tqdm(range(self.num_frames), desc=' -Frames', file=sys.stdout, ncols=80)
        else:
            framerange = range(self.num_frames)
        for n in framerange:
            buffer = fid_buffer.read(self.buffer_size)
            fid = np.frombuffer(buffer, dtype=self.dtype_code).reshape(self.fid_shape, order='F')
            fid = (fid[0] + 1j*fid[1])[np.newaxis, ...]
            volume = self._apply_nufft(fid, output_shape)
            if n == 0:
                self._recon_dtype = volume.dtype
            recon_buffer.write(volume.T.flatten(order='C').tobytes())
    
    def _apply_nufft(self, fid: np.ndarray, output_shape: list) -> np.ndarray:
        if self.nufft == 'sigpy':
            return self._sigpy_nufft(fid, output_shape)
        else:
            raise NotImplementedError

    def _sigpy_nufft(self, fid: np.ndarray, output_shape: list) -> np.ndarray:
        dcf = np.square(self.traj).sum(0).T
        return sp.nufft_adjoint(fid.squeeze().T * dcf, self.traj.T, oshape=output_shape)
    
    def _fid_correct_spoketiming(self) -> Tuple[str, int]:
        # parameters for spoke timing correction
        num_spokes = self.fid_shape[2]
        
        if self.verbose:
            print("\n++ Running spoke timing correction")
        
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False, dir=self.tmpdir) as stc_f:
            with self._get_fid() as fid_f:
                file_size = self._fid_get_filesize(fid_f)
                segs = self._fid_split_by_filesize(file_size, num_spokes)
                stc_buffer_size = self._fid_process_spoketiming(segs, fid_f, stc_f, num_spokes)
        self._buffers.append(stc_f)
        return stc_f.name, stc_buffer_size
    
    def _fid_get_filesize(self, fid_buffer: Union['BufferedReader', 'ZipExtFile']) -> float:
        if self.pvobj.is_compressed:
            fid_fname = os.path.basename(fid_buffer.name)
            fid_idx = [i for i, f in enumerate(self.pvobj._contents['files']) if fid_fname in f].pop()
            file_size = self.pvobj._contents['file_sizes'][fid_idx]
        else:
            file_size = os.fstat(fid_buffer.fileno()).st_size
        return ((file_size / self._num_frames) * self.num_frames) / 1024**3 # in GB
    
    def _fid_split_by_filesize(self, file_size: float, num_spokes: int) -> List[int]:
        num_segs = np.ceil(file_size / self.mem_limit).astype(int) if self.mem_limit else 1
        if self.verbose:
            print(f' + Size: {file_size:.3f} GB')
            print(f' + Split data into {num_segs} segments for saving memory.')

        num_spokes_per_seg = int(np.ceil(num_spokes / num_segs)) if num_segs > 1 else num_spokes
        if residual_spokes := num_spokes % num_spokes_per_seg:
            segs = [num_spokes_per_seg for _ in range(num_segs -1)] + [residual_spokes]
        else:
            segs = [num_spokes_per_seg for _ in range(num_segs)]
        return segs
    
    def _fid_process_spoketiming(self, segs: list[int], 
                                 fid_buffer: Union['BufferedReader', 'ZipExtFile'], 
                                 img_buffer: 'BufferedWriter', 
                                 num_spokes: int) -> int:
        num_echos = self.fid_shape[1]
        recon_buffer_offset = self.offset * self.buffer_size
        
        spoke_loc = 0
        stc_dtype = None
        stc_buffer_size = None
        
        if self.verbose:
            segrange = tqdm(segs, desc=' - Segments', file=sys.stdout, ncols=80)
        else:
            segrange = segs
        for seg_size in segrange:
            # load data
            spoke_buffer_size = int(self.buffer_size/num_spokes)
            spoke_offset = spoke_loc * spoke_buffer_size
            # total buffer size for current segment
            seg_buffer_size = spoke_buffer_size * seg_size
            seg = []
            for t in range(self.num_frames):
                frame_offset = t * self.buffer_size
                fid_buffer.seek(recon_buffer_offset + frame_offset + spoke_offset)
                seg.append(fid_buffer.read(seg_buffer_size))
            seg_shape = [2, num_echos, seg_size, self.num_frames]
            seg_data = np.frombuffer(b''.join(seg), dtype=self.dtype_code).reshape(seg_shape, order='F')
            # Spoke timing correction
            corrected_seg_data = self._fid_interpolate_segment(seg_data, seg_size, num_echos, 
                                                                  num_spokes, spoke_loc)
            
            # Store data
            for t in range(self.num_frames):
                frame_offset = t * self.buffer_size
                img_buffer.seek(frame_offset + spoke_offset)
                img_buffer.write(corrected_seg_data[:,:,:, t].flatten(order='F').tobytes())

            if not stc_dtype:
                stc_dtype = corrected_seg_data.dtype
                stc_buffer_size = np.prod(self.fid_shape) * stc_dtype.itemsize
            spoke_loc += seg_size
        return stc_buffer_size

    def _fid_interpolate_segment(self, 
                                 seg_data: np.ndarray, 
                                 seg_size: int, 
                                 num_echos: int, 
                                 num_spokes: int, 
                                 spoke_loc: int) -> np.ndarray:
        scan_time_per_vol = num_spokes * self.repetition_time
        target_timing = scan_time_per_vol / 2
        base_timestamps = np.arange(self.num_frames) * scan_time_per_vol
        target_timestamps = base_timestamps + target_timing
        corrected_seg_data = np.empty_like(seg_data)
        for spoke_id in range(seg_size):
            cur_spoke = spoke_loc + spoke_id
            ref_timestamps = base_timestamps + (cur_spoke * self.repetition_time)
            for c in range(2): # real and imaginary (complex)
                for e in range(num_echos):
                    interp_func = interp1d(ref_timestamps, 
                                        seg_data[c, e, spoke_id, :], 
                                        kind='linear',
                                        fill_value='extrapolate')
                    corrected_seg_data[c, e, spoke_id, :] = interp_func(target_timestamps)
        return corrected_seg_data
