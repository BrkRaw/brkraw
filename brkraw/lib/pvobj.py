import os
import zipfile as zf
import functools
from collections import namedtuple
from .parser import Parameter
from .utils import get_value

_2dseq = namedtuple('img_2dseq', ['reco_id', 'idx'])
_visu_pars = namedtuple('visu_pars', ['reco_id', 'idx'])
_reco = namedtuple('reco', ['reco_id', 'idx'])


class PvDatasetBase():
    path = None
    _subject = None
    _fid = None
    _method = None
    _acqp = None
    _avail_scanid = None
    _avail_recoid = None

    def __init__(self, path):
        self._reset()

    def _reset(self):
        self._fid = dict()
        self._method = dict()
        self._acqp = dict()
        self._visu_pars = dict()
        self._reco = dict()
        self._2dseq = dict()

    def _update_studyinfo(self):
        if self._subject is not None:
            subject = self._subject
            self.user_account   = subject.headers['OWNER']
            self.subj_id        = get_value(subject, 'SUBJECT_id')
            self.study_id       = get_value(subject, 'SUBJECT_study_nr')
            self.session_id     = get_value(subject, 'SUBJECT_study_name')
            self.subj_entry     = get_value(subject, 'SUBJECT_entry').split('_')[-1]
            self.subj_pose      = get_value(subject, 'SUBJECT_position').split('_')[-1]
            self.subj_sex       = get_value(subject, 'SUBJECT_sex')
            self.subj_type      = get_value(subject, 'SUBJECT_type')
            self.subj_weight    = get_value(subject, 'SUBJECT_weight')
            self.subj_dob       = get_value(subject, 'SUBJECT_dbirth')
            self.user_name      = get_value(subject, 'SUBJECT_name_string')
        else:
            self.user_account   = None
            self.subj_id        = None
            self.study_id       = None
            self.session_id     = None
            self.subj_entry     = None
            self.subj_pose      = None
            self.subj_sex       = None
            self.subj_type      = None
            self.subj_weight    = None
            self.subj_dob       = None
            self.user_name      = None

    def _parse_info(self):
        pass

    @property
    def avail_scan_id(self):
        self._avail_scanid = sorted(self._visu_pars.keys())
        return self._avail_scanid

    @property
    def avail_reco_id(self):
        self._avail_recoid = {}
        for scan_id in self.avail_scan_id:
            try:
                self._avail_recoid[scan_id] = sorted(list(map(lambda x: x.reco_id, self._visu_pars[scan_id])))
            except:
                self.avail_scan_id.remove(scan_id)
        return self._avail_recoid

    def _open_binary(self, path):
        pass

    def _open_string(self, path):
        pass

    def get_dataobj(self, scan_id, reco_id):
        import numpy as np
        from .reference import BYTEORDER, WORDTYPE
        from .utils import get_value, is_all_element_same

        # parse datatype
        visu_pars = self.get_visu_pars(scan_id, reco_id)
        dtype_code = np.dtype('{}{}'.format(BYTEORDER[get_value(visu_pars, 'VisuCoreByteOrder')],
                                            WORDTYPE[get_value(visu_pars, 'VisuCoreWordType')]))
        # load dataobject
        _2dseq = np.frombuffer(self.get_2dseq(scan_id, reco_id), dtype_code)

        # Below code had integrated into header instead changing the value
        # correction data slope and offset
        # data_slp = get_value(visu_pars, 'VisuCoreDataSlope')
        # if isinstance(data_slp, list):
        #     data_slp = data_slp[0] if is_all_element_same(data_slp) else data_slp
        # data_off = get_value(visu_pars, 'VisuCoreDataOffs')
        # if isinstance(data_off, list):
        #     data_off = data_off[0] if is_all_element_same(data_off) else data_off
        # try:
        #     recovered_2dseq = _2dseq * data_slp + data_off
        # except:
        #     raise Exception('size mismatch between data with slope or offset parameter.')
        # return recovered_2dseq
        return _2dseq

    def get_fid(self, scan_id):
        return self._open_binary(self._fid[scan_id])

    def get_2dseq(self, scan_id, reco_id):
        # return 2dseq binary string
        for tpl in filter(functools.partial(lambda x, y: True if x.reco_id == y else False,
                                            y=reco_id), self._2dseq[scan_id]):
            return self._open_binary(tpl.idx)

    def get_visu_pars(self, scan_id, reco_id):
        for tpl in filter(functools.partial(lambda x, y: True if x.reco_id == y else False,
                                            y=reco_id), self._visu_pars[scan_id]):
            return Parameter(self._open_string(tpl.idx))

    def get_reco(self, scan_id, reco_id):
        for tpl in filter(functools.partial(lambda x, y: True if x.reco_id == y else False,
                                            y=reco_id), self._reco[scan_id]):
            return Parameter(self._open_string(tpl.idx))

    def __repr__(self):
        return 'PvDataset( storageLocation: "{}" )'.format(self.path)

    def __del__(self):
        self.close()

    def close(self):
        pass


class PvDatasetDir(PvDatasetBase):
    def __init__(self, path):
        super(PvDatasetDir, self).__init__(path)
        self.__path = path
        self.path = os.path.basename(path)
        self._parse_info()
        self._update_studyinfo()

    def _parse_info(self):
        self._reset()
        for root, subdir, files in os.walk(self.__path):
            if 'subject' in files:
                with open(os.path.join(root, 'subject'), 'r') as f:
                    self._subject = Parameter(f.read().split('\n'))
            elif 'method' in files and 'acqp' in files:
                scan_id = os.path.basename(root)
                if scan_id.isdigit():
                    with open(os.path.join(root, 'method'), 'r') as f:
                        self._method[int(scan_id)] = Parameter(f.read().split('\n'))
                    with open(os.path.join(root, 'acqp'), 'r') as f:
                        self._acqp[int(scan_id)] = Parameter(f.read().split('\n'))
                    fid_path = os.path.join(root, 'fid')
                    if os.path.exists(fid_path):
                        self._fid[int(scan_id)] = os.path.join(root, 'fid')
            elif '2dseq' in files and 'visu_pars' in files:
                path_freg = root.split(os.path.sep)
                scan_id = path_freg[-3]
                reco_id = path_freg[-1]
                if scan_id.isdigit() and reco_id.isdigit():
                    if int(scan_id) in self._2dseq.keys():
                        self._2dseq[int(scan_id)].append(_2dseq(reco_id=int(reco_id),
                                                                idx=os.path.join(root, '2dseq')))
                    else:
                        self._2dseq[int(scan_id)] = [_2dseq(reco_id=int(reco_id),
                                                            idx=os.path.join(root, '2dseq'))]
                    if int(scan_id) in self._visu_pars.keys():
                        self._visu_pars[int(scan_id)].append(_visu_pars(reco_id=int(reco_id),
                                                                        idx=os.path.join(root, 'visu_pars')))
                    else:
                        self._visu_pars[int(scan_id)] = [_visu_pars(reco_id=int(reco_id),
                                                                    idx=os.path.join(root, 'visu_pars'))]
                    if int(scan_id) in self._reco.keys():
                        self._reco[int(scan_id)].append(_reco(reco_id=int(reco_id),
                                                              idx=os.path.join(root, 'reco')))
                    else:
                        self._reco[int(scan_id)] = [_reco(reco_id=int(reco_id),
                                                          idx=os.path.join(root, 'reco'))]

    def _open_binary(self, path):
        return open(path, 'rb').read()

    def _open_string(self, path):
        return open(path, 'r').read().split('\n')


class PvDatasetZip(zf.ZipFile, PvDatasetBase):
    def __init__(self, path):
        super(PvDatasetZip, self).__init__(path)
        self._parse_info()
        self._update_studyinfo()

    def _parse_info(self):
        self._reset()
        # parse subject information
        for idx, full_path in enumerate(self.namelist()):
            # path_freg = full_path.split(os.path.sep)
            path_freg = full_path.split('/') # zipfile uses / instead of os.sep
            n_freg = len(path_freg)

            if n_freg == 1:
                # database object
                pass

            elif n_freg == 2:
                if self.path is None:
                    self.path = path_freg[0]
                if path_freg[1] == 'subject':
                    with self.open(full_path) as f:
                        self._subject = Parameter(f.read().decode('UTF-8').split('\n'))

            elif n_freg == 3 and path_freg[1].isdigit():
                scan_id = int(path_freg[1])
                filename = path_freg[2]

                if filename == 'method':
                    with self.open(full_path) as f:
                        self._method[scan_id] = Parameter(f.read().decode('UTF-8').split('\n'))
                elif filename == 'acqp':
                    with self.open(full_path) as f:
                        self._acqp[scan_id] = Parameter(f.read().decode('UTF-8').split('\n'))
                elif filename == 'fid':
                    self._fid[scan_id] = idx
                else:
                    pass

            elif n_freg == 5 and path_freg[2] == 'pdata':
                scan_id = int(path_freg[1])
                if path_freg[3].isdigit():
                    reco_id = int(path_freg[3])
                    filename = path_freg[4]

                    if filename == '2dseq':
                        if scan_id in self._2dseq.keys():
                            self._2dseq[scan_id].append(_2dseq(reco_id=reco_id, idx=idx))
                        else:
                            self._2dseq[scan_id] = [_2dseq(reco_id=reco_id, idx=idx)]
                    elif filename == 'visu_pars':
                        if scan_id in self._visu_pars.keys():
                            self._visu_pars[scan_id].append(_visu_pars(reco_id=reco_id, idx=idx))
                        else:
                            self._visu_pars[scan_id] = [_visu_pars(reco_id=reco_id, idx=idx)]
                    elif filename == 'reco':
                        if scan_id in self._reco.keys():
                            self._reco[scan_id].append(_reco(reco_id=reco_id, idx=idx))
                        else:
                            self._reco[scan_id] = [_reco(reco_id=reco_id, idx=idx)]

    def _open_binary(self, path):
        return self.open(self.namelist()[path]).read()

    def _open_string(self, path):
        return self.open(self.namelist()[path]).read().decode('UTF-8').split('\n')