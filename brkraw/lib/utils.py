from .errors import UnexpectedError
from .reference import *
import re
import os
import numpy as np
from collections import OrderedDict
from functools import partial, reduce
from copy import copy as cp
import time


class TimeCounter:
    _start = None

    def __init__(self):
        self.reset()

    def reset(self):
        self._start = time.time()

    def time(self):
        return time.time() - self._start


def load_param(stringlist):
    # JCAMP DX parser
    params = OrderedDict()
    param_addresses = list()

    for line_num, line in enumerate(stringlist):
        regex_obj = re.match(ptrn_param, line)
        # if line is key=value pair
        if regex_obj is not None:
            # parse key and value
            key = re.sub(ptrn_param, r'\g<key>', line)
            value = re.sub(ptrn_param, r'\g<value>', line)
            # if key contains $
            if re.match(ptrn_key, key):
                # classify as parameter
                params[line_num] = PARAMETER, re.sub(ptrn_key, r'\g<key>', key), value
                param_addresses.append(line_num)
            else:
                # classify as file header
                params[line_num] = HEADER, key, value
                param_addresses.append(line_num)
    return params, param_addresses, stringlist


def convert_string_to(string):
    string = string.strip()
    if re.match(ptrn_string, string):
        string = re.sub(ptrn_string, r'\g<string>', string).strip()
    if not string:
        return None
    else:
        if re.match(ptrn_float, string):
            return float(string)
        elif re.match(ptrn_integer, string):
            return int(string)
        elif re.match(ptrn_engnotation, string):
            return float(string)
        else:
            return string


def convert_data_to(data, shape):
    # check if data is array
    if isinstance(data, str):
        is_bisarray = re.findall(ptrn_bisstring, data)
        if is_bisarray:
            is_bisarray = [convert_string_to(c) for c in is_bisarray]
            if len(is_bisarray) == 1:
                data = is_bisarray.pop()
            else:
                data = is_bisarray
        else:
            
            # [20210820] Add-paravision 360 related.
            m_all = re.findall(ptrn_at_array, data)
            m_all = set(m_all)
            m_all = list(m_all)

            for str_ptn in m_all:
                num_cnt = int(str_ptn[0])
                num_repeat = float(str_ptn[1])
                str_ptn = "@" + str_ptn[0] + "*(" + str_ptn[1] + ")"

                str_replace_old = str_ptn
                str_replace_new = [num_repeat for i in range(num_cnt)]
                str_replace_new = str(str_replace_new)
                str_replace_new = str_replace_new.replace(",", "")
                str_replace_new = str_replace_new.replace("[", "")
                str_replace_new = str_replace_new.replace("]", "")
                data = data.replace(str_replace_old, str_replace_new)
            
            if re.match(ptrn_complex_array, data):
                # data = re.sub(ptrn_complex_array, r'\g<comparray>', data)
                data_holder = cp(data)
                parser = {}
                level = 1
                while len(re.findall(ptrn_braces, data_holder)) != 0:
                    for parsed in re.finditer(ptrn_braces, data_holder):
                        key = 'level_{}'.format(level)

                        cont_parser = []
                        for cont in map(str.strip, parsed.group('contents').split(',')):
                            cont = convert_data_to(cont, -1)
                            if cont is not None:
                                cont_parser.append(cont)
                        if key not in parser.keys():
                            parser[key] = []
                        parser[key].append(cont_parser)
                        data_holder = data_holder.replace(parsed.group(0), '')
                    level += 1
                del level
                data = parser
            else:
                if re.match(ptrn_string, data):
                    data = re.sub(ptrn_string, r'\g<string>', data)
                else:
                    is_array = re.findall(ptrn_array, data)
                    # parse data shape
                    if shape is not -1:
                        shape = re.sub(ptrn_array, r'\g<array>', shape)
                        if ',' in shape:
                            shape = [convert_string_to(c) for c in shape.split(',')]

                    if is_array:
                        is_array = [convert_string_to(c) for c in is_array]
                        if any([',' in cell for cell in is_array]):
                            data = [[convert_string_to(c) for c in cell.split(',')] for cell in is_array]
                    else:
                        if ',' in data:
                            if re.findall(ptrn_arraystring, data):
                                data = [convert_string_to(c) for c in data.split(' ')]
                            else:
                                data = [convert_string_to(c) for c in data.split(',')]
                        else:
                            if ' ' in data:
                                data = [convert_string_to(c) for c in data.split(' ')]
    if isinstance(data, list):
        if isinstance(shape, list):
            if not any([isinstance(c, str) for c in data]):
                if not any([c is None for c in data]):
                    data = np.asarray(data).reshape(shape)
    elif isinstance(data, str):
        data = convert_string_to(data)
    return data


def get_value(pars, key):
    if key not in pars.parameters.keys():
        return None
    else:
        return pars.parameters[key]


def is_all_element_same(listobj):
    if listobj is None:
        return True
    else:
        return all(map(partial(lambda x, y: x == y, y=listobj[0]), listobj))


def is_numeric(x):
    return any([isinstance(x, float), isinstance(x, int)])


def multiply_all(list):
    return reduce(lambda x, y: x*y, list)


# META handler
def meta_get_value(value, acqp, method, visu_pars):
    if isinstance(value, str):
        return meta_check_source(value, acqp, method, visu_pars)
    elif isinstance(value, dict):
        if is_keywhere(value):
            return meta_check_where(value, acqp, method, visu_pars)
        elif is_keyindex(value):
            return meta_check_index(value, acqp, method, visu_pars)
        elif is_express(value):
            return meta_check_express(value, acqp, method, visu_pars)
        else:
            parser = dict()
            for k, v in value.items():
                parser[k] = meta_get_value(v, acqp, method, visu_pars)
            return parser
    elif isinstance(value, list):
        parser = []
        max_index = len(value) - 1
        for i, vi in enumerate(value):
            val = meta_get_value(vi, acqp, method, visu_pars)
            if val is not None:
                if val == vi:
                    if i == max_index:
                        parser.append(val)
                else:
                    parser.append(val)
        if len(parser) > 0:
            return parser[0]
        else:
            return None
    else:
        return value


def is_keywhere(value):
    if all([k in value.keys() for k in ['key', 'where']]):
        return True
    else:
        return False


def is_keyindex(value):
    if all([k in value.keys() for k in ['key', 'idx']]):
        return True
    else:
        return False


def is_express(value):
    if any([k in value.keys() for k in ['Equation']]):
        return True
    else:
        return False


def meta_check_where(value, acqp, method, visu_pars):
    val = meta_get_value(value['key'], acqp, method, visu_pars)
    if val is not None:
        if isinstance(value['where'], str):
            if value['where'] not in val:
                return None
            else:
                return val.index(value['where'])
        else:
            where = meta_get_value(value['where'], acqp, method, visu_pars)
            return val.index(where)
    else:
        return None


def meta_check_index(value, acqp, method, visu_pars):
    val = meta_get_value(value['key'], acqp, method, visu_pars)
    if val is not None:
        if isinstance(value['idx'], int):
            return val[value['idx']]
        else:
            idx = meta_get_value(value['idx'], acqp, method, visu_pars)
        if idx is not None:
            return val[idx]
        else:
            return None
    else:
        return None


def meta_check_express(value, acqp, method, visu_pars):
    lcm = locals()
    for k, v in value.items():
        if k != 'Equation':
            exec('global {}'.format(k))
            val = meta_get_value(v, acqp, method, visu_pars)
            exec('{} = {}'.format(k, val))
    try:
        exec("output = {}".format(value['Equation']), globals(), lcm)
        return lcm['output']
    except:
        return None


def meta_check_source(key_string, acqp, method, visu_pars):
    pool = [acqp, method, visu_pars]
    key_exist = [key_string in p.parameters.keys() for p in pool]
    for i, ans in enumerate(key_exist):
        if ans:
            return get_value(pool[i], key_string)
    return key_string


def yes_or_no(question):
    while True:
        reply = str(input(question + ' (y/n): ')).lower().strip()
        if reply[:1] == 'y':
            return True
        elif reply[:1] == 'n':
            return False
        else:
            print('  The answer is invalid!')


def convert_unit(size_in_bytes, unit):
    """ Convert the size from bytes to other units like KB, MB or GB"""
    size = float(size_in_bytes)
    if unit == 1:
        return size / 1024
    elif unit == 2:
        return size / (1024 * 1024)
    elif unit == 3:
        return size / (1024 * 1024 * 1024)
    elif unit == 4:
        return size / (1024**unit)
    else:
        return int(size)


def get_dirsize(dir_path):
    unit_dict = {0: 'B',
                 1: 'KB',
                 2: 'MB',
                 3: 'GB',
                 4: 'TB'}
    dir_size = 0
    for root, dirs, files in os.walk(dir_path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp):
                dir_size += os.path.getsize(fp)

    unit = int(len(str(dir_size)) / 3)
    return convert_unit(dir_size, unit), unit_dict[unit]


def get_filesize(file_path):
    unit_dict = {0: 'B',
                 1: 'KB',
                 2: 'MB',
                 3: 'GB'}
    file_size = os.path.getsize(file_path)

    unit = int(len(str(file_size)) / 3)
    return convert_unit(file_size, unit), unit_dict[unit]


def bids_validation(df, idx, key, val, num_char_allowed, dtype=None):
    import string
    from shleeh.errors import InvalidValueInField
    col = string.ascii_uppercase[df.columns.tolist().index(key)]
    special_char = re.compile(r'[^0-9a-zA-Z]')
    str_val = str(val)
    loc = 'col,row:[{},{}]'.format(col, idx + 2)
    if len(str_val) > num_char_allowed:
        message = "{} You can't use more than {} characters.".format(loc, num_char_allowed)
        raise InvalidValueInField(message)
    matched = special_char.search(str_val)
    if matched is not None:
        if ' ' in matched.group():
            message = "{} Empty string is not allowed.".format(loc)
        else:
            message = "{} Special characters are not allowed.".format(loc)
        raise InvalidValueInField(message)
    if dtype is not None:
        try:
            dtype(val)
        except:
            message = "{} Invalid data type. Value must be {}.".format(loc, dtype.__name__)
            raise InvalidValueInField(message)
    return True


def get_bids_ref_obj(ref_path, row):
    import json
    from shleeh.errors import InvalidApproach
    if os.path.exists(ref_path) and ref_path.lower().endswith('.json'):
        ref_data = json.load(open(ref_path))
        ref = ref_data['common']
        if row.modality in ['bold', 'cbv', 'epi']:
            if 'func' in ref_data.keys():
                for k, v in ref_data['func'].items():
                    if k in ref.keys():
                        raise InvalidApproach('Duplicated key is found at func: {}'.format(k))
                    else:
                        ref[k] = v
        # the below may not optimal for Bruker system,
        # only fieldmap and magnitude
        if row.modality in ['fieldmap', 'phase1', 'phase2',
                            'phasediff', 'magnitude',
                            'magnitude1', 'magnitude2']:
            if 'fmap' in ref_data.keys():
                for k, v in ref_data['fmap'].items():
                    if k in ref.keys():
                        raise InvalidApproach('Duplicated key is found at func: {}'.format(k))
                    else:
                        ref[k] = v
    else:
        ref = None
    return ref


def build_bids_json(dset, row, fname, json_path, slope=False, offset=False):
    import pandas as pd

    if pd.notnull(row.Start) or pd.notnull(row.End):
        crop = [int(row.Start), int(row.End)]
    else:
        crop = None
    if dset.is_multi_echo(row.ScanID, row.RecoID):  # multi_echo
        nii_objs = dset.get_niftiobj(row.ScanID, row.RecoID, crop=crop, slope=slope, offset=offset)
        for echo, nii in enumerate(nii_objs):
            # caught a bug here for multiple echo, changed fname to currentFileName
            currentFileName = '{}_echo-{}_{}'.format(fname, echo + 1, row.modality)
            output_path = os.path.join(row.Dir, currentFileName)
            nii.to_filename('{}.nii.gz'.format(output_path))
            if json_path:
                ref = get_bids_ref_obj(json_path, row)
                dset.save_json(row.ScanID, row.RecoID, currentFileName, dir=row.Dir,
                               metadata=ref, condition=['me', echo])
    else:
        fname = '{}_{}'.format(fname, row.modality)
        dset.save_as(row.ScanID, row.RecoID, fname, dir=row.Dir, crop=crop, slope=slope, offset=offset)
        if re.search('dwi', row.modality, re.IGNORECASE):
            # DTI parameter (FSL style)
            dset.save_bdata(row.ScanID, fname, dir=row.Dir)
        if json_path:
            ref = get_bids_ref_obj(json_path, row)
            if re.search('fieldmap', row.modality, re.IGNORECASE):
                condition = ['fm', None]
            else:
                condition = None
            if re.search('magnitude', row.modality, re.IGNORECASE):
                pass  # magnitude data does not require JSON (BIDS)
            else:
                dset.save_json(row.ScanID, row.RecoID, fname, dir=row.Dir,
                               metadata=ref, condition=condition)


def encdir_code_converter(enc_param):
    # for PV 5.1, #TODO: incompleted code.
    if enc_param == 'col_dir':
        return ['read_enc', 'phase_enc']
    elif enc_param == 'row_dir':
        return ['phase_enc', 'read_enc']
    elif enc_param == 'col_slice_dir':
        return ['read_enc', 'phase_enc', 'slice_enc']
    elif enc_param == 'row_slice_dir':
        return ['phase_enc', 'read_enc', 'slice_enc']
    else:
        raise Exception(ERROR_MESSAGES['PhaseEncDir'])


def mkdir(path):
    try:
        os.stat(path)
    except FileNotFoundError or OSError:
        os.makedirs(path)
    except:
        raise UnexpectedError


# brkraw script
def set_rescale(args):
    if not args.ignore_rescale:
        if args.ignore_slope:
            slope = None
        else:
            slope = False
        if args.ignore_offset:
            offset = None
        else:
            offset = False
    else:
        slope = None
        offset = None
    return slope, offset


def save_meta_files(study, args, scan_id, reco_id, output_fname):
    method = study._pvobj._method[scan_id].parameters['Method']
    if re.search('dti', method, re.IGNORECASE):
        study.save_bdata(scan_id, output_fname)
    if args.bids:
        study.save_json(scan_id, reco_id, output_fname)
