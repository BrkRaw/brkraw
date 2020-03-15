import os, re
from .pvobj import PvDatasetDir, PvDatasetZip
from .utils import *
from .reference import ERROR_MESSAGES
import numpy as np
from copy import copy as cp

def load(path):
    import os
    import zipfile

    err_message = ERROR_MESSAGES['ImportError']

    if os.path.isdir(path):
        return PvDatasetDir(path)
    elif os.path.isfile(path):
        if zipfile.is_zipfile(path):
            return PvDatasetZip(path)
        else:
            raise Exception(err_message)
    else:
        raise Exception(err_message)


class BrukerLoader():
    def __init__(self, path):
        self._pvobj = load(path)

    def close(self):
        self._pvobj.close()
        self._pvobj = None

    def get_dataobj(self, scan_id, reco_id):
        return self._pvobj.get_dataobj(scan_id, reco_id)

    def get_fid(self, scan_id):
        return self._pvobj.get_fid(scan_id)

    # methods to dump data into file object
    ## - NifTi1
    def get_niftiobj(self, scan_id, reco_id):
        from nibabel import Nifti1Image
        visu_pars = self._get_visu_pars(scan_id, reco_id)
        method = self._method[scan_id]
        affine = self._get_affine(visu_pars, method)
        dataobj = self.get_dataobj(scan_id, reco_id)
        shape = self._get_matrix_size(visu_pars, dataobj)
        imgobj = dataobj.reshape(shape[::-1]).T

        if isinstance(affine, list):
            parser = []
            slice_info = self._get_slice_info(visu_pars)
            num_slice_packs = slice_info['num_slice_packs']
            for spack_idx in range(num_slice_packs):
                slice_info = self._get_slice_info(visu_pars)
                num_slices_each_pack = slice_info['num_slices_each_pack']
                start = int(spack_idx * num_slices_each_pack[spack_idx])
                end = start + num_slices_each_pack[spack_idx]
                seg_imgobj = imgobj[..., start:end]
                niiobj = Nifti1Image(seg_imgobj, affine[spack_idx])
                niiobj = self._set_default_header(niiobj, visu_pars, method)
                parser.append(niiobj)
            return parser

        niiobj = Nifti1Image(imgobj, affine)
        niiobj = self._set_default_header(niiobj, visu_pars, method)
        return niiobj

    def save_as(self, scan_id, reco_id, filename, dir='./', ext='nii.gz'):
        niiobj = self.get_niftiobj(scan_id, reco_id)
        if isinstance(niiobj, list):
            for i, nii in enumerate(niiobj):
                output_path = os.path.join(dir,
                                           '{}-{}.{}'.format(filename,
                                                             str(i+1).zfill(2), ext))
                nii.to_filename(output_path)
        else:
            output_path = os.path.join(dir, '{}.{}'.format(filename, ext))
            niiobj.to_filename(output_path)

    def _set_default_header(self, niiobj, visu_pars, method):
        slice_info = self._get_slice_info(visu_pars)
        niiobj.header.default_x_flip = False
        temporal_resol = self._get_temp_info(visu_pars)['temporal_resol']
        temporal_resol = float(temporal_resol) / 1000
        slice_order = get_value(method, 'PVM_ObjOrderScheme')
        acq_method = get_value(method, 'Method')

        data_slp = get_value(visu_pars, 'VisuCoreDataSlope')
        if isinstance(data_slp, list):
            data_slp = data_slp[0] if is_all_element_same(data_slp) else data_slp
        data_off = get_value(visu_pars, 'VisuCoreDataOffs')
        if isinstance(data_off, list):
            data_off = data_off[0] if is_all_element_same(data_off) else data_off

        if re.search('epi', acq_method, re.IGNORECASE) and not \
                re.search('dti', acq_method, re.IGNORECASE):

            niiobj.header.set_xyzt_units('mm', 'sec')
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
            niiobj.header.set_xyzt_units('mm', 'unknown')
        niiobj.header['qform_code'] = 1
        niiobj.header['sform_code'] = 0
        niiobj.header['scl_slope'] = data_slp
        niiobj.header['scl_inter'] = data_off
        return niiobj

    ## - FSL bval, bvec, and bmat
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
    def save_json(self, scan_id, reco_id, filename, dir='./'):
        """ Save JSON file with BIDS standard MR acquisition parameter

        Args:
            scan_id:    Scan ID
            reco_id:    Reco ID
            filename:   Filename to save (without extension)
            dir:        Dirname to save

        Returns: None
        """

        acqp        = self._acqp[scan_id]
        method      = self._method[scan_id]
        visu_pars   = self._get_visu_pars(scan_id, reco_id)

        json_obj = dict()
        encdir_dic = {0: 'i', 1: 'j', 2: 'k'}
        for k, v in METADATA_FILED_INFO.items():
            val = meta_get_value(v, acqp, method, visu_pars)
            if k in ['PhaseEncodingDirection', 'SliceEncodingDirection']:
                if val != None:
                    val = encdir_dic[val]

            if isinstance(val, np.ndarray):
                val = val.tolist()
            if isinstance(val, list):
                val = ','.join(map(str, val))
            json_obj[k] = val

        with open(os.path.join(dir, '{}.json'.format(filename)), 'w') as f:
            import json
            json.dump(json_obj, f)

    # method to parse information of each scan
    # methods of protocol specific
    # EPI
    def _get_temp_info(self, visu_pars):
        """return temporal resolution for each volume of image"""
        total_time = get_value(visu_pars, 'VisuAcqScanTime')
        frame_group_info = self._get_frame_group_info(visu_pars)
        parser = []
        if frame_group_info is not None:
            for id, fg in enumerate(frame_group_info['group_id']):
                if not re.search('slice', fg, re.IGNORECASE):
                    parser.append(frame_group_info['matrix_shape'][id])

        frame_size = multiply_all(parser) if len(parser) > 0 else 1
        return dict(temporal_resol=(total_time / frame_size),
                    num_frames=frame_size,
                    unit='msec')

    # DTI
    def _get_bdata(self, method):
        bval = get_value(method, 'PVM_DwEffBval')
        bvec = get_value(method, 'PVM_DwGradVec')
        bmat = get_value(method, 'PVM_DwBMat')
        return bval, bvec, bmat

    # Generals
    def _get_gradient_encoding_info(self, visu_pars):
        version = get_value(visu_pars, 'VisuVersion')

        def encdir_code_converter(enc_param):
            # for PV 5.1, #TODO: incompleted code.
            if enc_param == 'col_dir':
                return ['read_enc', 'phase_enc']
            elif enc_param == 'row_dir':
                return ['phase_enc', 'read_enc']
            elif enc_param == 'col_slice_dir':
                return ['read_enc', 'phase_enc', 'slice_enc']
            else:
                raise Exception(ERROR_MESSAGES['PhaseEncDir'])

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
            raise Exception(ERROR_MESSAGES['DimType'])
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

    def _get_slice_info(self, visu_pars):
        version = get_value(visu_pars, 'VisuVersion')
        frame_group_info = self._get_frame_group_info(visu_pars)
        num_slice_packs = None
        num_slices_each_pack = []
        slice_distances_each_pack = []

        if frame_group_info is None:
            num_slice_packs = 1
            # below will be 1 in 3D protocol
            num_slices_each_pack = [get_value(visu_pars, 'VisuCoreFrameCount')]
            # below will be size of slice_enc axis in 3D protocol
            slice_distances_each_pack = [get_value(visu_pars, 'VisuCoreFrameThickness')]
        else:
            frame_groups = frame_group_info['group_id']
            if version == 1: # PV 5.1 support
                phase_enc_dir = get_value(visu_pars, 'VisuAcqImagePhaseEncDir')
                phase_enc_dir = [phase_enc_dir[0]] if is_all_element_same(phase_enc_dir) else phase_enc_dir
                matrix_shape = frame_group_info['matrix_shape']
                frame_thickness = get_value(visu_pars, 'VisuCoreFrameThickness')
                num_slice_packs = len(phase_enc_dir)
                num_slice_frames = 0
                for id, fg in enumerate(frame_groups):
                    if re.search('slice', fg, re.IGNORECASE):
                        num_slice_frames += 1
                        if num_slice_frames > 2:
                            raise Exception(ERROR_MESSAGES['SlicePacksSlices'])
                        num_slices_each_pack.append(matrix_shape[id])
                slice_distances_each_pack = [frame_thickness for _ in range(num_slice_packs)]
            elif version == 3:
                num_slice_packs = get_value(visu_pars, 'VisuCoreSlicePacksDef')
                if num_slice_packs is None:
                    num_slice_packs = 1
                    # raise Exception(ERROR_MESSAGES['NoSlicePacksDef'])
                else:
                    num_slice_packs = num_slice_packs[0][1]

                slices_info_in_pack = get_value(visu_pars, 'VisuCoreSlicePacksSlices')
                slice_distance = get_value(visu_pars, 'VisuCoreSlicePacksSliceDist')
                num_slice_frames = 0
                for id, fg in enumerate(frame_groups):
                    if re.search('slice', fg, re.IGNORECASE):
                        num_slice_frames += 1
                        if num_slice_frames > 2:
                            raise Exception(ERROR_MESSAGES['SlicePacksSlices'])
                        try:
                            num_slices_each_pack = [slices_info_in_pack[id][1] for _ in range(num_slice_packs)]
                        except:
                            raise Exception(ERROR_MESSAGES['SlicePacksSlices'])
                        if isinstance(slice_distance, list):
                            slice_distances_each_pack = [slice_distance[id] for _ in range(num_slice_packs)]
                        elif isinstance(slice_distance, float) or isinstance(slice_distance, int):
                            slice_distances_each_pack = [slice_distance for _ in range(num_slice_packs)]
                        else:
                            raise Exception(ERROR_MESSAGES['SliceDistDatatype'])
            if len(slice_distances_each_pack) == 0:
                slice_distances_each_pack = [get_value(visu_pars, 'VisuCoreFrameThickness')]
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
            if len(orient_matrix) != slice_info['num_slice_packs']:
                raise Exception(ERROR_MESSAGES['NumOrientMatrix'])
            else:
                for id, _om in enumerate(orient_matrix):
                    om = np.asarray(_om).reshape([3, 3])
                    omatrix_parser.append(om)
                    oorder_parser.append(get_axis_orient(om))
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

        if num_slice_packs > 1:
            affine = []
            for slice_idx in range(num_slice_packs):
                sidx = orient_info['orient_order'][slice_idx].index(2)
                slice_orient = slice_orient_map[sidx]
                resol = spatial_info['spatial_resol'][slice_idx]
                rmat = orient_info['orient_matrix'][slice_idx]
                pose = orient_info['volume_position'][slice_idx]
                if is_reversed:
                    raise Exception(ERROR_MESSAGES['NotIntegrated'])
                    # TODO: The reversed disk does not integrated for the multiple slicepack data
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

        spatial_info = self._get_spatial_info(visu_pars)
        slice_info = self._get_slice_info(visu_pars)
        temporal_info = self._get_temp_info(visu_pars)

        matrix_size = spatial_info['matrix_size']
        num_temporal_frame = temporal_info['num_frames']
        num_slice_packs = slice_info['num_slice_packs']

        if num_slice_packs > 1:
            if is_all_element_same(matrix_size):
                matrix_size = list(matrix_size[0])
                total_num_slices = sum(slice_info['num_slices_each_pack'])
                matrix_size[-1] = total_num_slices
            else:
                raise Exception(ERROR_MESSAGES['DimSize'])
        else:
            matrix_size =  list(matrix_size[0])
            if num_temporal_frame > 1:
                matrix_size.append(num_temporal_frame)
        if dataobj is not None:
            dataobj_shape = dataobj.shape[0]
            if multiply_all(matrix_size) != dataobj_shape:
                print(matrix_size, dataobj_shape)
                raise Exception(ERROR_MESSAGES['DimSize'])
        return matrix_size

    def _get_disk_slice_order(self, visu_pars):
        # check disk_slice_order #
        _fo = get_value(visu_pars, 'VisuCoreDiskSliceOrder')
        if _fo in [None, 'disk_normal_slice_order']:
            disk_slice_order = 'normal'
        elif _fo == 'disk_reverse_slice_order':
            disk_slice_order = 'reverse'
        else:
            raise Exception(ERROR_MESSAGES['NotIntegrated'])
        return disk_slice_order

    def _get_visu_pars(self, scan_id, reco_id):
        return self._pvobj.get_visu_pars(scan_id, reco_id)

    def _get_frame_group_info(self, visu_pars):
        frame_group = get_value(visu_pars, 'VisuFGOrderDescDim')
        if frame_group == None:
            return None  # there are no frame group exist
        else:
            parser = dict(frame_type = get_value(visu_pars, 'VisuCoreFrameType'),
                          frame_size=0, matrix_shape=[],
                          group_id=[], group_comment=[],
                          dependent_vals=[])

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

    # properties of the class
    @property
    def _version(self):
        return None

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

    def get_scan_time(self, visu_pars=None):
        """

        Args:
            visu_pars:

        Returns:

        """
        import datetime as dt
        subject_date = get_value(self._subject, 'SUBJECT_date')
        subject_date = subject_date[0] if isinstance(subject_date, list) else subject_date
        pattern_1 = r'(\d{2}:\d{2}:\d{2})\s(\d{2}\s\w+\s\d{4})'
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

        return dict(date       = date,
                    start_time = start_time)

    # printing functions / help documents
    def print_bids(self, scan_id, reco_id):
        acqp = self._acqp[scan_id]
        method = self._method[scan_id]
        visu_pars = self._get_visu_pars(scan_id, reco_id)

        encdir_dic = {0: 'i', 1: 'j', 2: 'k'}
        for k, v in METADATA_FILED_INFO.items():
            n_tap = int(5 - int(len(k) / 8))
            if len(k) % 8 >= 7:
                n_tap -= 1

            tap = ''.join(['\t'] * n_tap)
            val = meta_get_value(v, acqp, method, visu_pars)
            if k in ['PhaseEncodingDirection', 'SliceEncodingDirection']:
                if val != None:
                    val = encdir_dic[val]

            if isinstance(val, np.ndarray):
                val = val.tolist()
            if isinstance(val, list):
                val = ', '.join(map(str, val))

            print('{}:{}{}'.format(k, tap, val))

    def summary(self):
        pvobj = self._pvobj
        user_account    = pvobj.user_account
        subj_id         = pvobj.subj_id
        study_id        = pvobj.study_id
        session_id      = pvobj.session_id
        user_name       = pvobj.user_name
        subj_entry      = pvobj.subj_entry
        subj_pose       = pvobj.subj_pose
        subj_sex        = pvobj.subj_sex
        subj_type       = pvobj.subj_type
        subj_weight     = pvobj.subj_weight
        subj_dob        = pvobj.subj_dob

        lines = []
        for i, (scan_id, recos) in enumerate(self._avail.items()):
            for j, reco_id in enumerate(recos):
                visu_pars = self._get_visu_pars(scan_id, reco_id)
                if i == 0:
                    sw_version    = get_value(visu_pars, 'VisuCreatorVersion')

                    title = 'Paravision {}'.format(sw_version)
                    lines.append(title)
                    lines.append('-' * len(title))

                    try:
                        datetime = self.get_scan_time()
                    except:
                        raise Exception('Empty dataset...')
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
                tr = get_value(visu_pars, 'VisuAcqRepetitionTime')
                tr = ','.join(map(str, tr)) if isinstance(tr, list) else tr
                te = get_value(visu_pars, 'VisuAcqEchoTime')
                te = 0 if te is None else te
                te = ','.join(map(str, te)) if isinstance(te, list) else te
                pixel_bw = get_value(visu_pars, 'VisuAcqPixelBandwidth')
                flip_angle = get_value(visu_pars, 'VisuAcqFlipAngle')
                param_values = [tr, te, pixel_bw, flip_angle]
                if j == 0:
                    params = "[ TR: {0} ms, TE: {1:.3f} ms, pixelBW: {2:.2f} Hz, FlipAngle: {3} degree]".format(*param_values)
                    protocol_name = get_value(visu_pars, 'VisuAcquisitionProtocol')
                    sequence_name = get_value(visu_pars, 'VisuAcqSequenceName')
                    lines.append('[{}]\t{}::{}::\n\t{}'.format(str(scan_id).zfill(3),
                                                          sequence_name,
                                                          protocol_name,
                                                          params))

                dim = self._get_dim_info(visu_pars)[0]
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
                             '         spatial_resol: {} (unit:{}), temporal_resol: {} (unit:{})'.format(str(reco_id).zfill(2), dim, size,
                                                                                         fov_size,
                                                                                         s_resol, s_unit,
                                                                                         t_resol, t_unit))
        lines.append('\n')
        print('\n'.join(lines))

