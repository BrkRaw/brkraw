from shleeh import *
from shleeh.errors import *

from .orient import build_affine_from_orient_info, reversed_pose_correction, get_origin
from .pvobj import PvDatasetDir, PvDatasetZip
from .utils import *
from .orient import to_matvec
from .reference import ERROR_MESSAGES, ISSUE_REPORT
import numpy as np
import zipfile
import pathlib
import os
import re
import warnings
np.set_printoptions(formatter={'float_kind':'{:f}'.format})


def load(path):
    path = pathlib.Path(path)
    if os.path.isdir(path):
        return PvDatasetDir(path)
    elif os.path.isfile(path):
        if zipfile.is_zipfile(path):
            return PvDatasetZip(path)
        else:
            raise FileNotValidError(path, DataType.PVDATASET)
    else:
        raise FileNotValidError(path, DataType.PVDATASET)


class BrukerLoader():
    """ The front-end handler for Bruker PvDataset

    This class is designed to use for handle PvDataset and optimized for PV 6.0.1, but
    also provide backward compatibility with PV 5.1. This class can import naive
    PvDataset with directory as well as compressed dataset by zip and Paravision 6.0.1
    (*.zip and *.PvDatasets).

    Attributes:
        num_scans (int): The number of scan objects on the loaded dataset.
        num_recos (int): The number of reco objects on the loaded dataset.
        is_pvdataset (bool): Return True if imported path is PvDataset, else False

    Methods:
        - get method for data object
        get_dataobj(scan_id, reco_id)
            return dataobj without reshape (numpy.array)
        get_fid(scan_id)
            return binary fid object
        get_niftiobj(scan_id, reco_id)
            return nibabel's NifTi1Image object

        - get method for parameter objects
        get_acqp(scan_id)
            return acqp parameter object
        get_method(scan_id)
            return method parameter object
        get_visu_pars(scan_id, reco_id)
            return visu_pars parameter object

        - get method for image parameters
        get_matrix_size(scan_id, reco_id)
            return matrix shape to reshape dataobj
        get_affine(scan_id, reco_id)
            return affine transform matrix
        get_bdata(scan_id, reco_id)
            return bmat, bvec, bval as string
        get_scan_time(visu_pars=None)
            return dictionary contains the datetime object for session initiate time
            if visu_pars parameter object is given, it will contains scan start time

        - method to generate files
        save_nifti(scan_id, reco_id, filename, dir='./', ext='nii.gz')
            generate NifTi1 file
        save_bdata(scan_id, filename, dir='./')
            generate FSL's Bdata files for DTI image processing
        save_json(scan_id, reco_id, filename, dir='./')
            generate JSON with given filename for BIDS MRI parameters

        - method to print meta information
        print_bids(scan_id, reco_id, fobj=None)
            print out BIDS MRI parameters defined at reference.py
            if fileobject is given, it will be written in file instead of stdout
        info(fobj=None)
            print out the PvDataset major parameters
            if fileobject is given, it will be written in file instead of stdout
    """
    def __init__(self, path):
        """ class method to initiate object.
        Args:
            path (str): Path of PvDataset.
        """
        self._pvobj = load(path)

        if (self.num_scans > 0) and (self._subject != None):
            self._is_pvdataset = True
        else:
            self._is_pvdataset = False

    @property
    def pvobj(self):
        return self._pvobj

    @property
    def num_scans(self):
        # [20210820] Add-paravision 360 related.
        # return len(self._pvobj._fid.keys())
        len_scans = len(self._pvobj._fid.keys())
        if len_scans > 0:
            return len_scans
        else:
            return len(self._pvobj._2dseq.keys())

    @property
    def num_recos(self):
        return sum([len(r) for r in self._avail.values()])

    @property
    def is_pvdataset(self):
        return self._is_pvdataset

    def close(self):
        self._pvobj.close()
        self._pvobj = None

    def get_affine(self, scan_id, reco_id):
        visu_pars = self._get_visu_pars(scan_id, reco_id)
        method = self._method[scan_id]
        return self._get_affine(visu_pars, method)

    def _get_dataobj(self, scan_id, reco_id):
        dataobj = self._pvobj.get_dataobj(scan_id, reco_id)
        return dataobj

    def _get_dataslp(self, visu_pars):
        """ Return data slope and offset for value correction
        Args:
            visu_pars:

        Returns:
            data_slp
            data_off
        """
        data_slp = get_value(visu_pars, 'VisuCoreDataSlope')
        data_off = get_value(visu_pars, 'VisuCoreDataOffs')
        if isinstance(data_slp, list):
            data_slp = data_slp[0] if is_all_element_same(data_slp) else data_slp
        if isinstance(data_off, list):
            data_off = data_off[0] if is_all_element_same(data_off) else data_off
        return data_slp, data_off

    def get_dataobj(self, scan_id, reco_id, slope=True, offset=True):
        """ Return dataobj that has 3D(spatial) + extra frame
        Args:
            scan_id: scan id
            reco_id: reco id
            slope: if True correct slope
        Returns:
            dataobj
        """
        visu_pars   = self._get_visu_pars(scan_id, reco_id)
        dim         = self._get_dim_info(visu_pars)[0]
        fg_info     = self._get_frame_group_info(visu_pars)
        matrix_size = self.get_matrix_size(scan_id, reco_id)
        dataobj = self._get_dataobj(scan_id, reco_id)
        group_id    = fg_info['group_id']

        data_slp, data_off = self._get_dataslp(visu_pars)

        if slope:
            # This option apply the slope to data array directly instead of header
            f = fg_info['frame_size']
            if isinstance(data_slp, list):
                if f != len(data_slp):
                    raise UnexpectedError(message='data_slp mismatch;{}'.format(ISSUE_REPORT))
                else:
                    if dim == 2:
                        x, y = matrix_size[:2]
                        _dataobj = dataobj.reshape([f, x * y]).T
                    elif dim == 3:
                        x, y, z = matrix_size[:3]
                        _dataobj = dataobj.reshape([f, x * y * z]).T
                    else:
                        raise UnexpectedError(message='Unexpected frame shape on DTI image;{}'.format(ISSUE_REPORT))
                dataobj = (_dataobj * data_slp).T
            else:
                dataobj = dataobj * data_slp

        if offset:
            # This option apply the offset to data array directly instead of header
            f = fg_info['frame_size']
            if isinstance(data_off, list):
                if f != len(data_off):
                    raise UnexpectedError(message='data_off mismatch;{}'.format(ISSUE_REPORT))
                else:
                    if dim == 2:
                        x, y = matrix_size[:2]
                        _dataobj = dataobj.reshape([f, x * y]).T
                    elif dim == 3:
                        x, y, z = matrix_size[:3]
                        _dataobj = dataobj.reshape([f, x * y * z]).T
                    else:
                        raise UnexpectedError(message='Unexpected frame shape on DTI image;{}'.format(ISSUE_REPORT))
                dataobj = (_dataobj + data_off).T
            else:
                dataobj = dataobj + data_off

        dataobj = dataobj.reshape(matrix_size[::-1]).T

        def swap_slice_axis(group_id_, dataobj_):
            """ swap slice axis to third axis """
            slice_code = 'FG_SLICE'
            if slice_code not in group_id_:
                pass
            else:
                slice_axis_ = group_id_.index(slice_code) + 2
                dataobj_ = np.swapaxes(dataobj_, 2, slice_axis_)
            return dataobj_

        if fg_info['frame_type'] is not None:
            if group_id[0] == 'FG_SLICE':
                pass

            elif group_id[0] == 'FG_ECHO':  # multi-echo
                if self.is_multi_echo(scan_id, reco_id):
                    # push echo to last axis for BIDS
                    if 'FG_SLICE' not in group_id:
                        dataobj = np.swapaxes(dataobj, dim, -1)
                    else:
                        slice_axis = group_id.index('FG_SLICE') + 2
                        dataobj = np.swapaxes(dataobj, slice_axis, -1)
                        dataobj = np.swapaxes(dataobj, 2, -1)

            elif group_id[0] in ['FG_DIFFUSION', 'FG_DTI', 'FG_MOVIE', 'FG_COIL',
                                 'FG_CYCLE', 'FG_COMPLEX', 'FG_CARDIAC_MOVIE']:
                dataobj = swap_slice_axis(group_id, dataobj)
            else:
                # the output data will have default matrix shape and order.
                warnings.warn('Unexpected frame group combination;{}'.format(ISSUE_REPORT), UserWarning)
        return dataobj

    def get_fid(self, scan_id):
        return self._pvobj.get_fid(scan_id)

    @property
    def get_visu_pars(self):
        return self._get_visu_pars

    def get_method(self, scan_id):
        return self._method[scan_id]

    def get_acqp(self, scan_id):
        return self._acqp[scan_id]

    def get_bdata(self, scan_id):
        method = self.get_method(scan_id)
        return self._get_bdata(method)

    def get_matrix_size(self, scan_id, reco_id):
        visu_pars = self._get_visu_pars(scan_id, reco_id)
        dataobj = self._get_dataobj(scan_id, reco_id)
        return self._get_matrix_size(visu_pars, dataobj)

    def is_multi_echo(self, scan_id, reco_id):
        visu_pars = self._get_visu_pars(scan_id, reco_id)
        fg_info = self._get_frame_group_info(visu_pars)
        group_id = fg_info['group_id']
        if 'FG_ECHO' in group_id and 'FieldMap' not in fg_info['group_comment']:  #FieldMap will be treated different
            return fg_info['matrix_shape'][group_id.index('FG_ECHO')]  # return number of echos
        else:
            return False

    # methods to dump data into file object
    ## - NifTi1
    def get_niftiobj(self, scan_id, reco_id, crop=None, slope=False, offset=False):
        """ return nibabel nifti object
        Args:
            scan_id:
            reco_id:
            crop:   frame crop range
            slope:  if True, slope correction, else, header update
            offset: if True, offset correction, else, header update
        Returns:
            nibabel.Nifti1Image
        """
        from nibabel import Nifti1Image
        visu_pars = self._get_visu_pars(scan_id, reco_id)
        method = self._method[scan_id]
        affine = self._get_affine(visu_pars, method)
        group_id = self._get_frame_group_info(visu_pars)['group_id']

        # if 'FG_DTI' in group_id:
        #     # DTI dataset has vector slope
        #     slope = True
        #     offset = True
        # Blow condition will cover DTI cases

        data_slp, data_off = self._get_dataslp(visu_pars)
        if isinstance(data_slp, list) and slope is not None:
            slope = True
            if isinstance(data_off, list) and offset is not None:
                offset = True

        imgobj = self.get_dataobj(scan_id, reco_id, slope=slope, offset=offset)
        # dataobj = self._get_dataobj(scan_id, reco_id)
        # shape = self._get_matrix_size(visu_pars, dataobj)
        # imgobj = dataobj.reshape(shape[::-1]).T

        if isinstance(affine, list):
            parser = []
            slice_info = self._get_slice_info(visu_pars)
            num_slice_packs = slice_info['num_slice_packs']

            for spack_idx in range(num_slice_packs):
                num_slices_each_pack = slice_info['num_slices_each_pack']
                start = int(spack_idx * num_slices_each_pack[spack_idx])
                end = start + num_slices_each_pack[spack_idx]
                seg_imgobj = imgobj[..., start:end]
                niiobj = Nifti1Image(seg_imgobj, affine[spack_idx])
                niiobj = self._set_nifti_header(niiobj, visu_pars, method, slope=slope, offset=offset)
                parser.append(niiobj)
            return parser
        
        if self.is_multi_echo(scan_id, reco_id):
            # multi-echo image must be splitted
            parser = []
            for e in range(imgobj.shape[-1]):
                imgobj_ = imgobj[..., e]
                if len(imgobj_.shape) > 4:
                    x, y, z = imgobj_.shape[:3]
                    f = multiply_all(imgobj_.shape[3:])
                    # all converted nifti must be 4D
                    imgobj_ = imgobj_.reshape([x, y, z, f])
                if crop is not None:
                    if crop[0] is None:
                        niiobj_ = Nifti1Image(imgobj_[..., :crop[1]], affine)
                    elif crop[1] is None:
                        niiobj_ = Nifti1Image(imgobj_[..., crop[0]:], affine)
                    else:
                        niiobj_ = Nifti1Image(imgobj_[..., crop[0]:crop[1]], affine)
                else:
                    niiobj_ = Nifti1Image(imgobj_, affine)
                niiobj_ = self._set_nifti_header(niiobj_, visu_pars, method, slope=slope, offset=offset)
                parser.append(niiobj_)
            return parser
        else:
            if len(imgobj.shape) > 4:
                x, y, z = imgobj.shape[:3]
                f = multiply_all(imgobj.shape[3:])
                # all converted nifti must be 4D
                imgobj = imgobj.reshape([x, y, z, f])
        if crop is not None:
            if crop[0] is None:
                niiobj = Nifti1Image(imgobj[..., :crop[1]], affine)
            elif crop[1] is None:
                niiobj = Nifti1Image(imgobj[..., crop[0]:], affine)
            else:
                niiobj = Nifti1Image(imgobj[..., crop[0]:crop[1]], affine)
        else:
            niiobj = Nifti1Image(imgobj, affine)
        niiobj = self._set_nifti_header(niiobj, visu_pars, method, slope=slope, offset=offset)
        return niiobj

    def get_sitkimg(self, scan_id, reco_id, slope=True, offset=True, is_vector=False):
        """ return SimpleITK image obejct instead Nibabel NIFTI obj"""
        try:
            import SimpleITK as sitk
        except ModuleNotFoundError:
            raise ModuleNotFoundError('The BrkRaw did not be installed with SimpleITK (optional requirement).\n'
                                      '\t\t\t\t\t Please install SimpleITK to activate this method.')

        visu_pars = self._get_visu_pars(scan_id, reco_id)
        method = self._method[scan_id]
        res = self._get_spatial_info(visu_pars)['spatial_resol']
        dataobj = self.get_dataobj(scan_id, reco_id, slope=slope, offset=offset)
        affine = self._get_affine(visu_pars, method)

        if isinstance(affine, list):
            parser = []
            slice_info = self._get_slice_info(visu_pars)
            num_slice_packs = slice_info['num_slice_packs']
            for spack_idx in range(num_slice_packs):
                num_slices_each_pack = slice_info['num_slices_each_pack']
                start = int(spack_idx * num_slices_each_pack[spack_idx])
                end = start + num_slices_each_pack[spack_idx]
                seg_imgobj = dataobj[..., start:end]
                sitkobj = sitk.GetImageFromArray(seg_imgobj.T)
                sitkaff = np.matmul(np.diag([-1, -1, 1, 1]), affine[spack_idx])
                sitkdir, sitkorg = to_matvec(sitkaff)
                sitkdir = sitkdir.dot(np.linalg.inv(np.diag(res[spack_idx])))
                sitkobj.SetDirection(sitkdir.flatten().tolist())
                sitkobj.SetOrigin(sitkorg)
                sitkobj.SetSpacing(res[spack_idx])
                parser.append(sitkobj)
            return parser

        affine = np.matmul(np.diag([-1, -1, 1, 1]), affine)  # RAS to LPS
        direction_, origin_ = to_matvec(affine)
        direction_ = direction_.dot(np.linalg.inv(np.diag(res[0])))
        imgobj = sitk.GetImageFromArray(dataobj.T, isVector=is_vector)

        if len(dataobj.shape) > 3:
            res = [list(res[0]) + [self._get_temp_info(visu_pars)['temporal_resol']]]
            direction = np.eye(4)
            direction[:3, :3] = direction_
            direction = direction.flatten()
            origin = np.zeros([4])
            origin[:3] = origin_
        else:
            direction = direction_
            origin = origin_
        imgobj.SetDirection(direction.flatten().tolist())
        imgobj.SetOrigin(origin)
        imgobj.SetSpacing(res[0])
        # header update
        imgobj = self._set_dicom_header(imgobj, visu_pars, method, slope, offset)
        return imgobj

    def _set_dicom_header(self, sitk_img, visu_pars, method, slope, offset):
        """ TODO: need to update sitk header (DICOM format) """
        return sitk_img

    def save_sitk(self, io_type=None):
        """ TODO: mha, nrrd format with header """
        pass

    @property
    def save_as(self):
        return self.save_nifti

    def _inspect_ids(self, scan_id, reco_id):
        if scan_id not in self._avail.keys():
            print('[Error] Invalid Scan ID.\n'
                  '  - Your input: {}\n'
                  '  - Available Scan IDs: {}'.format(scan_id, list(self._avail.keys())))
            raise ValueError
        else:
            if reco_id not in self._avail[scan_id]:
                print('[Error] Invalid Reco ID.\n'
                      '  - Your input: {}\n'
                      '  - Available Reco IDs: {}'.format(reco_id, self._avail[scan_id]))
                raise ValueError

    def save_nifti(self, scan_id, reco_id, filename, dir='./', ext='nii.gz',
                crop=None, slope=False, offset=False):
        niiobj = self.get_niftiobj(scan_id, reco_id, crop=crop, slope=slope, offset=offset)
        if isinstance(niiobj, list):
            for i, nii in enumerate(niiobj):
                output_path = os.path.join(dir,
                                           '{}-{}.{}'.format(filename,
                                                             str(i+1).zfill(2), ext))
                nii.to_filename(output_path)
        else:
            output_path = os.path.join(dir, '{}.{}'.format(filename, ext))
            niiobj.to_filename(output_path)

    # - FSL bval, bvec, and bmat
    def save_bdata(self, scan_id, filename, dir='./'):
        method = self._method[scan_id]
        bval, bvec, bmat = self._get_bdata(method)
        output_path = os.path.join(dir, filename)

        with open('{}.bval'.format(output_path), 'w') as bval_fobj:
            for item in bval:
                bval_fobj.write("%f " % item)
            bval_fobj.write("\n")

        with open('{}.bvec'.format(output_path), 'w') as bvec_fobj:
            for row in bvec:
                for item in row:
                    bvec_fobj.write("%f " % item)
                bvec_fobj.write("\n")

        with open('{}.bmat'.format(output_path), 'w') as bmat_fobj:
            for row in bmat:
                for item in row.flatten():
                    bmat_fobj.write("%s " % item)
                bmat_fobj.write("\n")

    # BIDS JSON
    def _parse_json(self, scan_id, reco_id, metadata=None):
        acqp = self._acqp[scan_id]
        method = self._method[scan_id]
        visu_pars = self._get_visu_pars(scan_id, reco_id)

        json_obj = dict()
        encdir_dic = {0: 'i', 1: 'j', 2: 'k'}

        if metadata is None:
            metadata = COMMON_META_REF.copy()
        for k, v in metadata.items():
            val = meta_get_value(v, acqp, method, visu_pars)
            if k in ['PhaseEncodingDirection', 'SliceEncodingDirection']:
                # Convert the encoding direction meta data into BIDS format
                if val is not None:
                    if isinstance(val, int):
                        val = encdir_dic[val]
                    else:
                        if isinstance(val, list):
                            if is_all_element_same(val):
                                val = val[0]
                            else:
                                # handling condition of multiple phase encoding direction
                                updated_val = []
                                for v in val:
                                    if isinstance(v, int):
                                        # in PV 6 if each slice package has distinct phase encoding direction
                                        updated_val.append(encdir_dic[v])
                                    else:
                                        # in PV 5.1, element wise code conversion
                                        encdirs = encdir_code_converter(v)
                                        if 'phase_enc' in encdirs:
                                            pe_idx = encdirs.index('phase_enc')
                                            updated_val.append(encdir_dic[pe_idx])
                                        else:
                                            updated_val.append(None)
                                val = updated_val
                        elif isinstance(val, str):
                            # in PV 5.1, single value code conversion
                            encdirs = encdir_code_converter(val)
                            if 'phase_enc' in encdirs:
                                pe_idx = encdirs.index('phase_enc')
                                val = encdir_dic[pe_idx]
                            else:
                                val = None
                        else:
                            raise UnexpectedError('Unexpected phase encoding direction in PV5.1.')
            if isinstance(val, np.ndarray):
                val = val.tolist()
            json_obj[k] = val
        return json_obj

    def save_json(self, scan_id, reco_id, filename, dir='./', metadata=None, condition=None):
        json_obj = self._parse_json(scan_id, reco_id, metadata)
        if condition is not None:
            code, idx = condition
            if code == 'me':    # multi-echo
                if 'EchoTime' in json_obj.keys():
                    te = json_obj['EchoTime']
                    if isinstance(te, list):
                        json_obj['EchoTime'] = te[idx]
                    else:
                        raise InvalidApproach('SingleTE data')
            elif code == 'fm':
                visu_pars = self._get_visu_pars(scan_id, reco_id)
                json_obj['Units'] = get_value(visu_pars, 'VisuCoreDataUnits')[0]
                json_obj['IntendFor'] = ["func/*_bold.nii.gz"]
            else:
                raise InvalidApproach('Invalid datatype code for json creation')

        # remove all null fields
        for k, v in json_obj.items():
            if v is None:
                json_obj[k] = 'Value was not specified'
            
        # RepetitionTime is mutually exclusive with VolumeTiming, here default with RepetitionTime. 
        # https://bids-specification.readthedocs.io/en/latest/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#required-fields
        # To use VolumeTiming, remove the RepetitionTime item in .json file generated from bids_helper.

        if ('RepetitionTime' in json_obj.keys()) and ('VolumeTiming' in json_obj.keys()):
            if type(json_obj['RepetitionTime']) == int or type(json_obj['RepetitionTime']) == float:
                del json_obj['VolumeTiming']
                msg = "Both 'RepetitionTime' and 'VolumeTiming' exist in your .json file, removed 'VolumeTiming' to make it valid for BIDS.\
                \n To use VolumeTiming, remove the RepetitionTime item but keep VolumeTiming from the .json file generated from bids_helper."
                warnings.warn(msg)

        with open(os.path.join(dir, '{}.json'.format(filename)), 'w') as f:
            import json
            json.dump(json_obj, f, indent=4)

    def get_scan_time(self, visu_pars=None):
        import datetime as dt
        subject_date = get_value(self._subject, 'SUBJECT_date')
        subject_date = subject_date[0] if isinstance(subject_date, list) else subject_date
        pattern_1 = r'(\d{2}:\d{2}:\d{2})\s+(\d+\s\w+\s\d{4})'
        pattern_2 = r'(\d{4}-\d{2}-\d{2})[T](\d{2}:\d{2}:\d{2})'
        if re.match(pattern_1, subject_date):
            # start time
            start_time = dt.time(*map(int, re.sub(pattern_1, r'\1', subject_date).split(':')))
            # date
            date = dt.datetime.strptime(re.sub(pattern_1, r'\2', subject_date), '%d %b %Y').date()
            # end time
            if visu_pars is not None:
                last_scan_time = get_value(visu_pars, 'VisuAcqDate')
                last_scan_time = dt.time(*map(int, re.sub(pattern_1, r'\1', last_scan_time).split(':')))
                acq_time = get_value(visu_pars, 'VisuAcqScanTime') / 1000.0
                time_delta = dt.timedelta(0, acq_time)
                scan_time = (dt.datetime.combine(date, last_scan_time) + time_delta).time()
                return dict(date=date,
                            start_time=start_time,
                            scan_time=scan_time)
        elif re.match(pattern_2, subject_date):
            # start time
            # subject_date = get_value(self._subject, 'SUBJECT_date')[0]
            start_time = dt.time(*map(int, re.sub(pattern_2, r'\2', subject_date).split(':')))
            # date
            date = dt.date(*map(int, re.sub(pattern_2, r'\1', subject_date).split('-')))

            # end date
            if visu_pars is not None:
                scan_time = get_value(visu_pars, 'VisuCreationDate')[0]
                scan_time = dt.time(*map(int, re.sub(pattern_2, r'\2', scan_time).split(':')))
                return dict(date=date,
                            start_time=start_time,
                            scan_time=scan_time)
        else:
            raise Exception(ERROR_MESSAGES['NotIntegrated'])

        return dict(date=date,
                    start_time=start_time)

    # printing functions / help documents
    def print_bids(self, scan_id, reco_id, fobj=None, metadata=None):
        if fobj == None:
            import sys
            fobj = sys.stdout
        json_obj = self._parse_json(scan_id, reco_id, metadata)
        for k, val in json_obj.items():
            n_tap = int(5 - int(len(k) / 8))
            if len(k) % 8 >= 7:
                n_tap -= 1
            tap = ''.join(['\t'] * n_tap)
            print('{}:{}{}'.format(k, tap, val), file=fobj)

    def info(self, io_handler=None):
        """ Prints out the information of the internal contents in Bruker raw data
        Args:
            io_handler: IO handler where to print out
        """
        if io_handler == None:
            import sys
            io_handler = sys.stdout

        pvobj = self._pvobj
        user_account = pvobj.user_account
        subj_id = pvobj.subj_id
        study_id = pvobj.study_id
        session_id = pvobj.session_id
        user_name = pvobj.user_name
        subj_entry = pvobj.subj_entry
        subj_pose = pvobj.subj_pose
        subj_sex = pvobj.subj_sex
        subj_type = pvobj.subj_type
        subj_weight = pvobj.subj_weight
        subj_dob = pvobj.subj_dob

        lines = []
        for i, (scan_id, recos) in enumerate(self._avail.items()):
            for j, reco_id in enumerate(recos):
                visu_pars = self._get_visu_pars(scan_id, reco_id)
                if i == 0:
                    sw_version = get_value(visu_pars, 'VisuCreatorVersion')

                    title = 'Paravision {}'.format(sw_version)
                    lines.append(title)
                    lines.append('-' * len(title))

                    try:
                        datetime = self.get_scan_time()
                    except:
                        datetime = dict(date='None')
                        # raise Exception('Empty dataset...')
                    lines.append('UserAccount:\t{}'.format(user_account))
                    lines.append('Date:\t\t{}'.format(datetime['date']))
                    lines.append('Researcher:\t{}'.format(user_name))
                    lines.append('Subject ID:\t{}'.format(subj_id))
                    lines.append('Session ID:\t{}'.format(session_id))
                    lines.append('Study ID:\t{}'.format(study_id))
                    lines.append('Date of Birth:\t{}'.format(subj_dob))
                    lines.append('Sex:\t\t{}'.format(subj_sex))
                    lines.append('Weight:\t\t{} kg'.format(subj_weight))
                    lines.append('Subject Type:\t{}'.format(subj_type))
                    lines.append('Position:\t{}\t\tEntry:\t{}'.format(subj_pose, subj_entry))

                    lines.append('\n[ScanID]\tSequence::Protocol::[Parameters]')
                # try:
                tr = get_value(visu_pars, 'VisuAcqRepetitionTime')
                tr = ','.join(map(str, tr)) if isinstance(tr, list) else tr
                te = get_value(visu_pars, 'VisuAcqEchoTime')
                te = 0 if te is None else te
                te = ','.join(map(str, te)) if isinstance(te, list) else te
                pixel_bw = get_value(visu_pars, 'VisuAcqPixelBandwidth')
                flip_angle = get_value(visu_pars, 'VisuAcqFlipAngle')
                param_values = [tr, te, pixel_bw, flip_angle]
                for k, v in enumerate(param_values):
                    if v is None:
                        param_values[k] = ''
                    if isinstance(v, float):
                        param_values[k] = '{0:.2f}'.format(v)
                if j == 0:
                    params = "[ TR: {0} ms, TE: {1} ms, pixelBW: {2} Hz, FlipAngle: {3} degree]".format(
                        *param_values)
                    protocol_name = get_value(visu_pars, 'VisuAcquisitionProtocol')
                    sequence_name = get_value(visu_pars, 'VisuAcqSequenceName')
                    lines.append('[{}]\t{}::{}::\n\t{}'.format(str(scan_id).zfill(3),
                                                               sequence_name,
                                                               protocol_name,
                                                               params))

                dim, cls = self._get_dim_info(visu_pars)
                if cls == 'spatial_only':
                    size = self._get_matrix_size(visu_pars)
                    size = ' x '.join(map(str, size))
                    spatial_info = self._get_spatial_info(visu_pars)
                    temp_info = self._get_temp_info(visu_pars)
                    s_resol = spatial_info['spatial_resol']
                    fov_size = spatial_info['fov_size']
                    fov_size = ' x '.join(map(str, fov_size))
                    s_unit = spatial_info['unit']
                    t_resol = '{0:.3f}'.format(temp_info['temporal_resol'])
                    t_unit = temp_info['unit']
                    s_resol = list(s_resol[0]) if is_all_element_same(s_resol) else s_resol
                    s_resol = ' x '.join(['{0:.3f}'.format(r) for r in s_resol])

                    lines.append('    [{}] dim: {}D, matrix_size: {}, fov_size: {} (unit:mm)\n'
                                 '         spatial_resol: {} (unit:{}), temporal_resol: {} (unit:{})'.format(
                        str(reco_id).zfill(2), dim, size,
                        fov_size,
                        s_resol, s_unit,
                        t_resol, t_unit))
                else:
                    lines.append('    [{}] dim: {}, {}'.format(str(reco_id).zfill(2), dim, cls))
        lines.append('\n')
        print('\n'.join(lines), file=io_handler)

    # method to parse information of each scan
    # methods of protocol specific

    def _set_nifti_header(self, niiobj, visu_pars, method, slope, offset):
        slice_info = self._get_slice_info(visu_pars)
        niiobj.header.default_x_flip = False
        temporal_resol = self._get_temp_info(visu_pars)['temporal_resol']
        temporal_resol = float(temporal_resol) / 1000
        slice_order = get_value(method, 'PVM_ObjOrderScheme')
        acq_method = get_value(method, 'Method')

        data_slp, data_off = self._get_dataslp(visu_pars)

        if re.search('epi', acq_method, re.IGNORECASE) and not \
                re.search('dti', acq_method, re.IGNORECASE):

            niiobj.header.set_xyzt_units(xyz=2, t=8)
            niiobj.header['pixdim'][4] = temporal_resol
            niiobj.header.set_dim_info(slice=2)
            num_slices = slice_info['num_slices_each_pack'][0]
            niiobj.header['slice_duration'] = temporal_resol / num_slices

            if slice_order == 'User_defined_slice_scheme':
                niiobj.header['slice_code'] = 0
            elif slice_order == 'Sequential':
                niiobj.header['slice_code'] = 1
            elif slice_order == 'Reverse_sequential':
                niiobj.header['slice_code'] = 2
            elif slice_order == 'Interlaced':
                niiobj.header['slice_code'] = 3
            elif slice_order == 'Reverse_interlacesd':
                niiobj.header['slice_code'] = 4
            elif slice_order == 'Angiopraphy':
                niiobj.header['slice_code'] = 0
            else:
                raise Exception(ERROR_MESSAGES['NotIntegrated'])
            niiobj.header['slice_start'] = 0
            niiobj.header['slice_end'] = num_slices - 1
        else:
            niiobj.header.set_xyzt_units('mm')
        niiobj.header['qform_code'] = 1
        niiobj.header['sform_code'] = 0
        if not slope:
            if slope is not None:
                if isinstance(data_slp, list):
                    raise InvalidApproach('Invalid slope size;'
                                          'The vector type scl_slope cannot be set in nifti header.')
                niiobj.header['scl_slope'] = data_slp
            else:
                niiobj.header['scl_slope'] = 1
        else:
            niiobj.header['scl_slope'] = 1
        if not offset:
            if offset is not None:
                if isinstance(data_off, list):
                    raise InvalidApproach('Invalid offset size;'
                                          'The vector type scl_offset cannot be set in nifti header.')
                niiobj.header['scl_inter'] = data_off
            else:
                niiobj.header['scl_inter'] = 0
        else:
            niiobj.header['scl_inter'] = 0
        return niiobj

    # EPI
    def _get_temp_info(self, visu_pars):
        """return temporal resolution for each volume of image"""
        total_time = get_value(visu_pars, 'VisuAcqScanTime')
        fg_info = self._get_frame_group_info(visu_pars)
        parser = []
        if fg_info['frame_type'] is not None:
            for id, fg in enumerate(fg_info['group_id']):
                if not re.search('slice', fg, re.IGNORECASE):
                    parser.append(fg_info['matrix_shape'][id])
        frame_size = multiply_all(parser) if len(parser) > 0 else 1
        if total_time is None:  # derived reco data
            total_time = 0
        return dict(temporal_resol=(total_time / frame_size),
                    num_frames=frame_size,
                    unit='msec')

    # DTI
    @staticmethod
    def _get_bdata(method):
        bval = get_value(method, 'PVM_DwEffBval')
        bvec = get_value(method, 'PVM_DwGradVec').T # to have three rows instead of three columns
        bmat = get_value(method, 'PVM_DwBMat')
        return bval, bvec, bmat

    # Generals
    @staticmethod
    def _get_gradient_encoding_info(visu_pars):
        version = get_value(visu_pars, 'VisuVersion')

        if version == 1:  # case PV 5.1, prepare compatible form of variable
            phase_enc = get_value(visu_pars, 'VisuAcqImagePhaseEncDir')
            phase_enc = phase_enc[0] if is_all_element_same(phase_enc) else phase_enc
            if isinstance(phase_enc, list) and len(phase_enc) > 1:
                encoding_axis = []
                for d in phase_enc:
                    encoding_axis.append(encdir_code_converter(d))
            else:
                encoding_axis = encdir_code_converter(phase_enc)
        else:  # case PV 6.0.1
            encoding_axis = get_value(visu_pars, 'VisuAcqGradEncoding')
        return encoding_axis

    def _get_dim_info(self, visu_pars):
        """check if the frame contains only spatial components"""
        dim      = get_value(visu_pars, 'VisuCoreDim')
        dim_desc = get_value(visu_pars, 'VisuCoreDimDesc')

        if not all(map(lambda x: x == 'spatial', dim_desc)):
            if 'spectroscopic' in dim_desc:
                return dim, 'contain_spectroscopic'  # spectroscopic data
            elif 'temporal' in dim_desc:
                return dim, 'contain_temporal'  # unexpected data
        else:
            return dim, 'spatial_only'

    def _get_spatial_info(self, visu_pars):
        dim, dim_type = self._get_dim_info(visu_pars)
        if dim_type != 'spatial_only':
            if dim != 1:
                raise Exception(ERROR_MESSAGES['DimType'])
            else:
                # experimental approaches
                matrix_size = get_value(visu_pars, 'VisuCoreSize')
                fov_size    = get_value(visu_pars, 'VisuCoreExtent')
                voxel_resol = np.divide(fov_size, matrix_size).tolist()
            return dict(spatial_resol = [voxel_resol],
                        matrix_size = [matrix_size],
                        fov_size    = fov_size,
                        unit        = 'mm',
                        )
        else:
            matrix_size = get_value(visu_pars, 'VisuCoreSize')
            fov_size    = get_value(visu_pars, 'VisuCoreExtent')
            voxel_resol = np.divide(fov_size, matrix_size).tolist()
            slice_resol = self._get_slice_info(visu_pars)

            if dim == 3:
                spatial_resol = [voxel_resol]
                matrix_size = [matrix_size]
            elif dim == 2:
                xr, yr = voxel_resol
                xm, ym = matrix_size
                spatial_resol = [(xr, yr, zr) for zr in slice_resol['slice_distances_each_pack']]
                matrix_size   = [(xm, ym, zm) for zm in slice_resol['num_slices_each_pack']]
            else:
                raise Exception(ERROR_MESSAGES['DimSize'])
            return dict(spatial_resol = spatial_resol,
                        matrix_size   = matrix_size,
                        fov_size=fov_size,
                        unit          = 'mm',
                        )

    def _get_slice_info(self, visu_pars, method=None):
        version = get_value(visu_pars, 'VisuVersion')
        fg_info = self._get_frame_group_info(visu_pars)
        num_slice_packs = None
        num_slices_each_pack = []
        slice_distances_each_pack = []

        if fg_info['frame_type'] is None:
            num_slice_packs = 1
            # below will be 1 in 3D protocol
            num_slices_each_pack = [get_value(visu_pars, 'VisuCoreFrameCount')]
            # below will be size of slice_enc axis in 3D protocol
            slice_distances_each_pack = [get_value(visu_pars, 'VisuCoreFrameThickness')]
        else:
            frame_groups = fg_info['group_id']
            if version == 1: # PV 5.1 support
                try:
                    phase_enc_dir = get_value(visu_pars, 'VisuAcqImagePhaseEncDir')
                    phase_enc_dir = [phase_enc_dir[0]] if is_all_element_same(phase_enc_dir) else phase_enc_dir
                    num_slice_packs = len(phase_enc_dir)
                except:
                    num_slice_packs = 1
                matrix_shape = fg_info['matrix_shape']
                frame_thickness = get_value(visu_pars, 'VisuCoreFrameThickness')
                num_slice_frames = 0
                # for id, fg in enumerate(frame_groups):
                for _, fg in enumerate(frame_groups):
                    if re.search('slice', fg, re.IGNORECASE):
                        num_slice_frames += 1
                        if num_slice_frames > 2:
                            raise Exception(ERROR_MESSAGES['SlicePacksSlices'])
                        if num_slice_packs > 1:
                            for s in range(num_slice_packs):
                                # num_slices_each_pack.append(int(matrix_shape[id]/num_slice_packs))
                                num_slices_each_pack.append(int(matrix_shape[0]/num_slice_packs))
                        else:
                            # num_slices_each_pack.append(matrix_shape[id])
                            num_slices_each_pack.append(matrix_shape[0])
                slice_distances_each_pack = [frame_thickness for _ in range(num_slice_packs)]
            # [20210822] Add version 4
            #elif version == 3:
            elif version == 3 or version == 4 or version == 5:
                num_slice_packs = get_value(visu_pars, 'VisuCoreSlicePacksDef')
                if num_slice_packs is None:
                    num_slice_packs = 1
                    # raise Exception(ERROR_MESSAGES['NoSlicePacksDef'])
                else:
                    num_slice_packs = num_slice_packs[0][1]

                slices_info_in_pack = get_value(visu_pars, 'VisuCoreSlicePacksSlices')
                slice_distance = get_value(visu_pars, 'VisuCoreSlicePacksSliceDist')
                num_slice_frames = 0
                # for id, fg in enumerate(frame_groups):
                for _, fg in enumerate(frame_groups):
                    if re.search('slice', fg, re.IGNORECASE):
                        num_slice_frames += 1
                        if num_slice_frames > 2:
                            raise Exception(ERROR_MESSAGES['SlicePacksSlices'])
                        try:
                            # num_slices_each_pack = [slices_info_in_pack[id][1] for _ in range(num_slice_packs)]
                            num_slices_each_pack = [slices_info_in_pack[0][1] for _ in range(num_slice_packs)]
                        except:
                            raise Exception(ERROR_MESSAGES['SlicePacksSlices'])
                        if isinstance(slice_distance, list):
                            # slice_distances_each_pack = [slice_distance[id] for _ in range(num_slice_packs)]
                            slice_distances_each_pack = [slice_distance[0] for _ in range(num_slice_packs)]
                        elif isinstance(slice_distance, float) or isinstance(slice_distance, int):
                            slice_distances_each_pack = [slice_distance for _ in range(num_slice_packs)]
                        else:
                            raise Exception(ERROR_MESSAGES['SliceDistDatatype'])
            if len(slice_distances_each_pack) == 0:
                slice_distances_each_pack = [get_value(visu_pars, 'VisuCoreFrameThickness')]
            else:
                for i, d in enumerate(slice_distances_each_pack):
                    if d == 0:
                        slice_distances_each_pack[i] = get_value(visu_pars, 'VisuCoreFrameThickness')
            if len(num_slices_each_pack) == 0:
                num_slices_each_pack = [1]

        return dict(num_slice_packs            = num_slice_packs,
                    num_slices_each_pack       = num_slices_each_pack,
                    slice_distances_each_pack  = slice_distances_each_pack,
                    unit_slice_distances       = 'mm'
                    )

    def _get_orient_info(self, visu_pars, method):

        def get_axis_orient(orient_matrix):
            """return indice of axis orientation profiles"""
            return [np.argmax(abs(orient_matrix[:, 0])),
                    np.argmax(abs(orient_matrix[:, 1])),
                    np.argmax(abs(orient_matrix[:, 2]))]

        omatrix_parser  = []
        oorder_parser   = []
        vposition_parser = []

        orient_matrix = get_value(visu_pars, 'VisuCoreOrientation').tolist()
        slice_info = self._get_slice_info(visu_pars)
        slice_position = get_value(visu_pars, 'VisuCorePosition')
        subj_position = get_value(visu_pars, 'VisuSubjectPosition')
        gradient_orient = get_value(method, 'PVM_SPackArrGradOrient')

        if slice_info['num_slice_packs'] > 1:
            num_ori_mat = len(orient_matrix)
            num_slice_packs = slice_info['num_slice_packs']
            if num_ori_mat != num_slice_packs:
                mpms = True
                if not num_slice_packs % num_ori_mat:
                    raise Exception(ERROR_MESSAGES['NumOrientMatrix'])
                else:
                    # multi slice packs and multi slices, each slice packs must be identical on element.
                    # TODO: If error occurred it means the existing of exception for this.
                    cut_idx = 0
                    num_slices = int(num_ori_mat / num_slice_packs)
                    _orient_matrix = []
                    _slice_position = []
                    for ci in range(num_slice_packs):
                        om_set = orient_matrix[cut_idx:cut_idx + num_slices]
                        sp_set = slice_position[cut_idx:cut_idx + num_slices]
                        if is_all_element_same(om_set):
                            _orient_matrix.append(om_set[0])
                            _slice_position.append(sp_set)
                        else:
                            raise Exception(ERROR_MESSAGES['NumOrientMatrix'])
                        cut_idx += num_slices
                orient_matrix = _orient_matrix
                slice_position = _slice_position
            else:
                mpms = False

            for id, _om in enumerate(orient_matrix):
                om = np.asarray(_om).reshape([3, 3])
                omatrix_parser.append(om)
                oorder_parser.append(get_axis_orient(om))
                if mpms:
                    vposition_parser.append(get_origin(slice_position[id], gradient_orient))
                else:
                    vposition_parser.append(slice_position[id])

        else:
            # check num_slices of first slice_pack
            if is_all_element_same(orient_matrix):
                orient_matrix = orient_matrix[0]
            else:
                raise Exception(ERROR_MESSAGES['NumOrientMatrix'])
            try:
                slice_position = get_origin(slice_position, gradient_orient)
            except:
                raise Exception(ERROR_MESSAGES['NumSlicePosition'])

            omatrix_parser = np.asarray(orient_matrix).reshape([3, 3])
            oorder_parser = get_axis_orient(omatrix_parser)
            vposition_parser = slice_position

        return dict(subject_type = get_value(visu_pars, 'VisuSubjectType'),
                    subject_position = subj_position,
                    volume_position = vposition_parser,
                    orient_matrix = omatrix_parser,
                    orient_order  = oorder_parser,
                    gradient_orient = gradient_orient,
                    )

    def _get_affine(self, visu_pars, method):
        is_reversed = True if self._get_disk_slice_order(visu_pars) == 'reverse' else False
        slice_info = self._get_slice_info(visu_pars)
        spatial_info = self._get_spatial_info(visu_pars)
        orient_info = self._get_orient_info(visu_pars, method)
        slice_orient_map = {0: 'sagital', 1: 'coronal', 2: 'axial'}
        num_slice_packs = slice_info['num_slice_packs']
        subj_pose = orient_info['subject_position']
        subj_type = orient_info['subject_type']

        ## Rollback below changes upon comment on issue #10
        # version = get_value(visu_pars, 'VisuVersion')
        # if version == 1:  # PV 5.1 required the position correction
        #     subj_pose = orient_info['subject_position']
        # else:             # PV 6.01 does not
        #     subj_pose = None

        if num_slice_packs > 1:
            affine = []
            for slice_idx in range(num_slice_packs):
                sidx = orient_info['orient_order'][slice_idx].index(2)
                slice_orient = slice_orient_map[sidx]
                resol = spatial_info['spatial_resol'][slice_idx]
                rmat = orient_info['orient_matrix'][slice_idx]
                pose = orient_info['volume_position'][slice_idx]
                if is_reversed:
                    raise UnexpectedError('Invalid VisuCoreDiskSliceOrder;'
                                          'The multi-slice-packs dataset reversed is not tested data.'
                                          '{}'.format(ISSUE_REPORT))
                affine.append(build_affine_from_orient_info(resol, rmat, pose,
                                                            subj_pose, subj_type,
                                                            slice_orient))
        else:
            sidx = orient_info['orient_order'].index(2)
            slice_orient = slice_orient_map[sidx]
            resol = spatial_info['spatial_resol'][0]
            rmat = orient_info['orient_matrix']
            pose = orient_info['volume_position']
            if is_reversed:
                distance = slice_info['slice_distances_each_pack']
                pose = reversed_pose_correction(pose, rmat, distance)
            affine = build_affine_from_orient_info(resol, rmat, pose,
                                                   subj_pose, subj_type,
                                                   slice_orient)
        return affine

    def _get_matrix_size(self, visu_pars, dataobj=None):

        spatial_info        = self._get_spatial_info(visu_pars)
        slice_info          = self._get_slice_info(visu_pars)
        temporal_info       = self._get_temp_info(visu_pars)
        # patch the case of multi-echo
        fg_info             = self._get_frame_group_info(visu_pars)

        matrix_size         = spatial_info['matrix_size']
        num_temporal_frame  = temporal_info['num_frames']
        num_slice_packs     = slice_info['num_slice_packs']

        if num_slice_packs > 1:
            if is_all_element_same(matrix_size):
                matrix_size         = list(matrix_size[0])
                total_num_slices    = sum(slice_info['num_slices_each_pack'])
                matrix_size[-1]     = total_num_slices
            else:
                raise UnexpectedError('Matrix size mismatch with multi-slice-packs dataobj;'
                                      '{}{}'.format(matrix_size, ISSUE_REPORT))
        else:
            matrix_size = list(matrix_size[0])
            if 'FG_SLICE' in fg_info['group_id']:
                if fg_info['group_id'].index('FG_SLICE'):  # in the case the slicing frame group happen later
                    matrix_size     = matrix_size[:2]
                    matrix_size.extend(fg_info['matrix_shape'])
                else:
                    if num_temporal_frame > 1:
                        matrix_size.append(num_temporal_frame)
            else:
                if num_temporal_frame > 1:
                    matrix_size.append(num_temporal_frame)

        if dataobj is not None:
            # matrix size inspection
            dataobj_shape = dataobj.shape[0]
            if multiply_all(matrix_size) != dataobj_shape:
                raise UnexpectedError('Matrix size mismatch with dataobj;'
                                      '{} != {}{}'.format(multiply_all(matrix_size),
                                                          dataobj_shape,
                                                          ISSUE_REPORT))
        return matrix_size

    @staticmethod
    def _get_disk_slice_order(visu_pars):
        # check disk_slice_order #
        _fo = get_value(visu_pars, 'VisuCoreDiskSliceOrder')
        if _fo in [None, 'disk_normal_slice_order']:
            disk_slice_order = 'normal'
        elif _fo == 'disk_reverse_slice_order':
            disk_slice_order = 'reverse'
        else:
            raise UnexpectedError('Invalid VisuCoreDiskSliceOrder:{};{}'.format(_fo, ISSUE_REPORT))
        return disk_slice_order

    def _get_visu_pars(self, scan_id, reco_id):
        # test validation of scan_id and reco_id here
        self._inspect_ids(scan_id, reco_id)
        return self._pvobj.get_visu_pars(scan_id, reco_id)

    @staticmethod
    def _get_frame_group_info(visu_pars):
        frame_group = get_value(visu_pars, 'VisuFGOrderDescDim')
        parser = dict(frame_type=None,
                      frame_size=0, matrix_shape=[],
                      group_id=[], group_comment=[],
                      dependent_vals=[])
        if frame_group is None:
            # there are no frame group exist
            return parser
        else:
            parser['frame_type'] = get_value(visu_pars, 'VisuCoreFrameType')
            for idx, d in enumerate(get_value(visu_pars, 'VisuFGOrderDesc')):
                (num_fg_elements, fg_id, fg_commt,
                 valsStart, valsCnt) = d
                # calsCnt = Number of dependent parameters
                # valsStart = index of starting of dependent parameter (described in 'VisuGroupDepVals')
                # e.g. if calcCnt is 2, and valsStart is 1, parameter index will be 1, and 2
                parser['matrix_shape'].append(num_fg_elements)
                parser['group_id'].append(fg_id)
                parser['group_comment'].append(fg_commt)
                parser['dependent_vals'].append([])
                if valsCnt > 0:
                    for i in range(valsCnt):
                        parser['dependent_vals'][idx].append(get_value(visu_pars, 'VisuGroupDepVals')[valsStart + i])
            parser['frame_size'] = reduce(lambda x, y: x * y, parser['matrix_shape'])
            return parser

    @property
    def _subject(self):
        return self._pvobj._subject

    @property
    def _acqp(self):
        return self._pvobj._acqp

    @property
    def _method(self):
        return self._pvobj._method

    @property
    def _avail(self):
        return self._pvobj.avail_reco_id

