# -*- coding: utf-8 -*-
from shleeh import *
from shleeh.errors import *

from .. import BrukerLoader, __version__
from ..lib.utils import set_rescale, save_meta_files, mkdir
import argparse
import os, re

_supporting_bids_ver = '1.2.2'


def main():
    parser = argparse.ArgumentParser(prog='brkraw',
                                     description="BrkRaw command-line interface")
    parser.add_argument("-v", "--version", action='version', version='%(prog)s v{}'.format(__version__))

    subparsers = parser.add_subparsers(title='Sub-commands',
                                       description='To run this command, you must specify one of the functions listed'
                                                   'below next to the command. For more information on each function, '
                                                   'use -h next to the function name to call help document.',
                                       help='description',
                                       dest='function',
                                       metavar='command')

    input_str = "input raw Bruker data"
    input_dir_str = "input directory that contains multiple raw Bruker data"
    output_dir_str = "output directory name"
    output_fnm_str = "output filename"
    bids_opt = "create a JSON file contains metadata based on BIDS recommendation"

    info = subparsers.add_parser("info", help='Prints out the information of the internal contents in Bruker raw data')
    info.add_argument("input", help=input_str, type=str)

    gui = subparsers.add_parser("gui", help='Run GUI mode')
    nii = subparsers.add_parser("tonii", help='Convert a single raw Bruker data into NifTi file(s)')
    niiall = subparsers.add_parser("tonii_all", help="Convert All raw Bruker data located in the input directory")
    bids_helper = subparsers.add_parser("bids_helper", help="Creates a BIDS datasheet "
                                                            "for guiding BIDS data converting.")
    bids_convert = subparsers.add_parser("bids_convert", help="Convert ALL raw Bruker data located "
                                                              "in the input directory based on the BIDS datasheet")

    gui.add_argument("-i", "--input", help=input_str, type=str, default=None)
    gui.add_argument("-o", "--output", help=output_dir_str, type=str, default=None)
    gui.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    gui.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    gui.add_argument("--ignore-rescale", help='remove slope and offset values from header', action='store_true')

    nii.add_argument("input", help=input_str, type=str)
    nii.add_argument("-b", "--bids", help=bids_opt, action='store_true')
    nii.add_argument("-o", "--output", help=output_fnm_str, type=str, default=False)
    nii.add_argument("-r", "--recoid", help="RECO ID (default=1), "
                                            "option to specify a particular reconstruction id to convert",
                     type=int, default=1)
    nii.add_argument("-s", "--scanid", help="Scan ID, option to specify a particular scan to convert.", type=str)
    nii.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    nii.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    nii.add_argument("--ignore-rescale", help='remove slope and offset values from header', action='store_true')

    niiall.add_argument("input", help=input_dir_str, type=str)
    niiall.add_argument("-o", "--output", help=output_dir_str, type=str)
    niiall.add_argument("-b", "--bids", help=bids_opt, action='store_true')
    niiall.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    niiall.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    niiall.add_argument("--ignore-rescale", help='remove slope and offset values from header', action='store_true')

    bids_helper.add_argument("input", help=input_dir_str, type=str)
    bids_helper.add_argument("output", help="output BIDS datasheet filename (.xlsx)", type=str)
    bids_helper.add_argument("-j", "--json", help="create JSON syntax template for "
                                                  "parsing metadata from the header", action='store_true')

    bids_convert.add_argument("input", help=input_dir_str, type=str)
    bids_convert.add_argument("datasheet", help="input BIDS datahseet filename", type=str)
    bids_convert.add_argument("-j", "--json", help="input JSON syntax template filename", type=str, default=False)
    bids_convert.add_argument("-o", "--output", help=output_dir_str, type=str, default=False)
    bids_convert.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    bids_convert.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    bids_convert.add_argument("--ignore-rescale", help='remove slope and offset values from header',
                              action='store_true')

    args = parser.parse_args()

    if args.function == 'info':
        path = args.input
        if any([os.path.isdir(path), ('zip' in path), ('PvDataset' in path)]):
            study = BrukerLoader(path)
            study.info()
        else:
            list_path = [d for d in os.listdir('.') if (any([os.path.isdir(d),
                                                             ('zip' in d),
                                                             ('PvDataset' in d)]) and re.search(path, d, re.IGNORECASE))]
            for p in list_path:
                study = BrukerLoader(p)
                study.info()

    elif args.function == 'gui':
        ipath = args.input
        opath = args.output
        from ..ui.main_win import MainWindow
        root = MainWindow()
        if ipath != None:
            root._path = ipath
            if not args.ignore_rescale:
                if args.ignore_slope:
                    root._ignore_slope = True
                else:
                    root._ignore_slope = False
                if args.ignore_offset:
                    root._ignore_offset = True
                else:
                    root._ignore_offset = False
            else:
                root._ignore_slope = True
                root._ignore_offset = True

            root._extend_layout()
            root._load_dataset()
        if opath != None:
            root._output = opath
        else:
            root._output = os.path.curdir
        root.mainloop()

    elif args.function == 'tonii':
        path = args.input
        scan_id = args.scanid
        reco_id = args.recoid
        study = BrukerLoader(path)
        slope, offset = set_rescale(args)

        if args.output:
            output = args.output
        else:
            output = '{}_{}'.format(study._pvobj.subj_id,study._pvobj.study_id)
        if scan_id:
            output_fname = '{}-{}-{}'.format(output, scan_id, reco_id)
            try:
                scan_id = int(scan_id)
                reco_id = int(reco_id)
                study.save_as(scan_id, reco_id, output_fname, slope=slope, offset=offset)
                save_meta_files(study, args, scan_id, reco_id, output_fname)
                print('NifTi file is generated... [{}]'.format(output_fname))
            except:
                print(f'Conversion failed: ScanID:{str(scan_id)}, RecoID:{str(reco_id)}')
        else:
            for scan_id, recos in study._pvobj.avail_reco_id.items():
                for reco_id in recos:
                    output_fname = '{}-{}-{}'.format(output, str(scan_id).zfill(2), reco_id)
                    try:
                        study.save_as(scan_id, reco_id, output_fname, slope=slope, offset=offset)
                        save_meta_files(study, args, scan_id, reco_id, output_fname)
                        print('NifTi file is genetared... [{}]'.format(output_fname))
                    except:
                        print(f'Conversion failed: ScanID:{str(scan_id)}, RecoID:{str(reco_id)}')

    elif args.function == 'tonii_all':
        from os.path import join as opj, isdir, isfile

        path = args.input
        slope, offset = set_rescale(args)
        invalid_error_message = f'[Error] Invalid input path: {path}\n'
        empty_folder = f'        The input path does not contain any raw data.'
        wrong_target = f'        The input path indicates raw data itself. \n' \
                       f'        You must input the parents folder instead of path of the raw data\n' \
                       f'        If you want to convert single session raw data, use (tonii) instead.'

        list_of_raw = sorted([d for d in os.listdir(path) if isdir(opj(path, d)) \
                              or (isfile(opj(path, d)) and (('zip' in d) or ('PvDataset' in d)))])
        if not len(list_of_raw):
            # raise error with message if the folder is empty (or does not contains any PvDataset)
            print(invalid_error_message, empty_folder)
            raise InvalidApproach(invalid_error_message)
        if not BrukerLoader(path).is_pvdataset:
            # raise error if the input path is identified as PvDataset
            print(invalid_error_message, wrong_target)
            raise InvalidApproach(invalid_error_message)

        base_path = args.output
        if not base_path:
            base_path = 'Data'
        mkdir(base_path)
        for raw in list_of_raw:
            sub_path = os.path.join(path, raw)
            study = BrukerLoader(sub_path)
            if study.is_pvdataset:
                if len(study._pvobj.avail_scan_id):
                    subj_path = os.path.join(base_path, 'sub-{}'.format(study._pvobj.subj_id))
                    mkdir(subj_path)
                    sess_path = os.path.join(subj_path, 'ses-{}'.format(study._pvobj.study_id))
                    mkdir(sess_path)
                    for scan_id, recos in study._pvobj.avail_reco_id.items():
                        method = study._pvobj._method[scan_id].parameters['Method']
                        if re.search('epi', method, re.IGNORECASE) and not re.search('dti', method, re.IGNORECASE):
                            output_path = os.path.join(sess_path, 'func')
                        elif re.search('dti', method, re.IGNORECASE):
                            output_path = os.path.join(sess_path, 'dwi')
                        elif re.search('flash', method, re.IGNORECASE) or re.search('rare', method, re.IGNORECASE):
                            output_path = os.path.join(sess_path, 'anat')
                        else:
                            output_path = os.path.join(sess_path, 'etc')
                        mkdir(output_path)
                        filename = 'sub-{}_ses-{}_{}'.format(study._pvobj.subj_id, study._pvobj.study_id,
                                                             str(scan_id).zfill(2))
                        for reco_id in recos:
                            output_fname = os.path.join(output_path, '{}_reco-{}'.format(filename,
                                                                                         str(reco_id).zfill(2)))
                            try:
                                study.save_as(scan_id, reco_id, output_fname, slope=slope, offset=offset)
                                save_meta_files(study, args, scan_id, reco_id, output_fname)
                            except:
                                print(f'Conversion failed: ScanID:{str(scan_id)}, RecoID:{str(reco_id)}')
                    print(f'{raw} is converted...')
                else:
                    print(f'{raw} does not contains any scan data to convert...')
            else:
                print(f'{raw} is not PvDataset.')

    elif args.function == 'bids_helper':
        import pandas as pd
        path = os.path.abspath(args.input)
        ds_output = os.path.abspath(args.output)

        make_json = args.json
        if not ds_output.endswith('.xlsx'):
            # to prevent pandas ValueError in case user does not provide valid file extension.
            output = f'{ds_output}.xlsx'
        else:
            output = ds_output

        Headers = ['RawData', 'SubjID', 'SessID', 'ScanID', 'RecoID', 'DataType',
                   'task', 'acq', 'ce', 'rec', 'dir', 'run', 'modality', 'Start', 'End']
        df = pd.DataFrame(columns=Headers)

        for dname in sorted(os.listdir(path)):
            dpath = os.path.join(path, dname)
            try:
                dset = BrukerLoader(dpath)
            except:
                dset = None

            if dset is not None:
                if dset.is_pvdataset:
                    pvobj = dset.pvobj

                    rawdata = pvobj.path
                    subj_id = pvobj.subj_id
                    sess_id = pvobj.session_id

                    for scan_id, recos in pvobj.avail_reco_id.items():
                        for reco_id in recos:
                            visu_pars = dset.get_visu_pars(scan_id, reco_id)
                            if dset._get_dim_info(visu_pars)[1] == 'spatial_only':
                                num_spack = dset._get_slice_info(visu_pars)['num_slice_packs']

                                if num_spack != 3:  # excluding localizer
                                    method = dset.get_method(scan_id).parameters['Method']
                                    if re.search('epi', method, re.IGNORECASE) and not re.search('dti', method, re.IGNORECASE):
                                        datatype = 'func'
                                    elif re.search('dti', method, re.IGNORECASE):
                                        datatype = 'dwi'
                                    elif re.search('flash', method, re.IGNORECASE) or re.search('rare', method, re.IGNORECASE):
                                        datatype = 'anat'
                                    elif re.search('fieldmap', method, re.IGNORECASE):
                                        datatype = 'fmap'
                                    else:
                                        datatype = 'etc'

                                    item = dict(zip(Headers, [rawdata, subj_id, sess_id, scan_id, reco_id, datatype]))
                                    if datatype == 'fmap':
                                        for m, s, e in [['fieldmap', 0, 1], ['magnitude', 1, 2]]:
                                            item['modality'] = m
                                            item['Start'] = s
                                            item['End'] = e
                                            df = df.append(item, ignore_index=True)
                                    elif datatype == 'dwi':
                                        item['modality'] = 'dwi'
                                        df = df.append(item, ignore_index=True)
                                    else:
                                        df = df.append(item, ignore_index=True)

        df.to_excel(output, index=None)

        if make_json:
            fname = output[:-5]
            json_fname = f'{fname}.json'
            print(f'Creating JSON syntax template for parsing the BIDS required metadata '
                  f'(BIDS v{_supporting_bids_ver}): {json_fname}')
            with open(json_fname, 'w') as f:
                import json
                from ..lib.reference import COMMON_META_REF, FMRI_META_REF, FIELDMAP_META_REF
                ref_dict = dict(common=COMMON_META_REF,
                                func=FMRI_META_REF,
                                fmap=FIELDMAP_META_REF)
                json.dump(ref_dict, f, indent=4)

        print('[Important notice] The function helps to minimize the BIDS organization but does not guarantee that '
              'the dataset always meets the BIDS requirements. '
              'Therefore, after converting your data, we recommend validating '
              'your dataset using an official BIDS validator.')

    elif args.function == 'bids_convert':
        import pandas as pd
        import numpy as np
        import json
        import datetime
        from ..lib.utils import build_bids_json, bids_validation

        pd.options.mode.chained_assignment = None
        path = args.input
        datasheet = args.datasheet
        output = args.output
        df = pd.read_excel(datasheet, dtype={'SubjID': str, 'SessID': str, 'run': str})
        json_fname = args.json
        slope, offset = set_rescale(args)

        # check if the project is multi-session
        if all(pd.isnull(df['SessID'])):
            # SessID was removed
            multi_session = False
        else:
            num_session = len(list(set(df['SessID'])))
            if num_session > 1:
                multi_session = True
            else:
                multi_session = False

        if not output:
            root_path = os.path.abspath(os.path.join(os.path.curdir, 'Data'))
        else:
            root_path = output

        mkdir(root_path)

        # prepare the required file for converted BIDS dataset
        data_des = 'dataset_description.json'
        readme = 'README'
        if not os.path.exists(data_des):
            with open(os.path.join(root_path, 'dataset_description.json'), 'w') as f:
                from ..lib.reference import DATASET_DESC_REF
                json.dump(DATASET_DESC_REF, f, indent=4)
        if not os.path.exists(readme):
            with open(os.path.join(root_path, readme), 'w') as f:
                f.write(f'This dataset has been converted using BrkRaw (v{__version__}) at {datetime.datetime.now()}.\n')
                f.write('## How to cite?\n - https://doi.org/10.5281/zenodo.3818615\n')

        print('Inspect input BIDS datasheet...')
        for dname in sorted(os.listdir(path)):
            dpath = os.path.join(path, dname)
            try:
                dset = BrukerLoader(dpath)
                if dset.is_pvdataset:
                    pvobj = dset.pvobj
                    rawdata = pvobj.path
                    filtered_dset = df[df['RawData'].isin([rawdata])].reset_index()
                    filtered_dset.loc[:, 'FileName'] = [np.nan] * len(filtered_dset)
                    filtered_dset.loc[:, 'Dir'] = [np.nan] * len(filtered_dset)

                    if len(filtered_dset):
                        subj_id = list(set(filtered_dset['SubjID']))[0]
                        subj_code = f'sub-{subj_id}'

                        for i, row in filtered_dset.iterrows():
                            if multi_session:
                                # If multi-session, make session dir
                                sess_code = f'ses-{row.SessID}'
                                subj_path = os.path.join(root_path, subj_code)
                                mkdir(subj_path)
                                subj_path = os.path.join(subj_path, sess_code)
                                mkdir(subj_path)
                                # add session info to filename as well
                                fname = f'{subj_code}_{sess_code}'
                            else:
                                subj_path = os.path.join(root_path, subj_code)
                                mkdir(subj_path)
                                fname = f'{subj_code}'

                            datatype = row.DataType
                            dtype_path = os.path.join(subj_path, datatype)
                            mkdir(dtype_path)

                            if pd.notnull(row.task):
                                if bids_validation(df, i, 'task', row.task, 10):
                                    fname = f'{fname}_task-{row.task}'
                            if pd.notnull(row.acq):
                                if bids_validation(df, i, 'acq', row.acq, 10):
                                    fname = f'{fname}_acq-{row.acq}'
                            if pd.notnull(row.ce):
                                if bids_validation(df, i, 'ce', row.ce, 5):
                                    fname = f'{fname}_ce-{row.ce}'
                            if pd.notnull(row.dir):
                                if bids_validation(df, i, 'dir', row.dir, 2):
                                    fname = f'{fname}_dir-{row.dir}'
                            if pd.notnull(row.rec):
                                if bids_validation(df, i, 'rec', row.rec, 2):
                                    fname = f'{fname}_rec-{row.rec}'
                            filtered_dset.loc[i, 'FileName'] = fname
                            filtered_dset.loc[i, 'Dir'] = dtype_path
                            if pd.isnull(row.modality):
                                method = dset.get_method(row.ScanID).parameters['Method']
                                if row.DataType == 'anat':
                                    if re.search('flash', method, re.IGNORECASE):
                                        modality = 'FLASH'
                                    elif re.search('rare', method, re.IGNORECASE):
                                        modality = 'T2w'
                                    else:
                                        modality = '{}'.format(method.split(':')[-1])
                                else:
                                    modality = '{}'.format(method.split(':')[-1])
                                filtered_dset.loc[i, 'modality'] = modality
                            else:
                                bids_validation(df, i, 'modality', row.modality, 10, dtype=str)

                        list_tested_fn = []
                        # Converting data according to the updated sheet
                        print(f'Converting {dname}...')

                        for i, row in filtered_dset.iterrows():
                            temp_fname = f'{row.FileName}_{row.modality}'
                            if temp_fname not in list_tested_fn:
                                # filter the DataFrame that has same filename (updated without run)
                                fn_filter = filtered_dset.loc[:, 'FileName'].isin([row.FileName])
                                fn_df = filtered_dset[fn_filter].reset_index(drop=True)

                                # filter specific modality from above DataFrame
                                md_filter = fn_df.loc[:, 'modality'].isin([row.modality])
                                md_df = fn_df[md_filter].reset_index(drop=True)

                                if len(md_df) > 1:
                                    conflict_tested = []
                                    for j, sub_row in md_df.iterrows():
                                        if pd.isnull(sub_row.run):
                                            fname = f'{sub_row.FileName}_run-{str(j+1).zfill(2)}'
                                        else:
                                            _ = bids_validation(df, i, 'run', sub_row.run, 3, dtype=int)
                                            fname = f'{sub_row.FileName}_run-{str(sub_row.run).zfill(2)}'
                                        if fname in conflict_tested:
                                            raise ValueConflictInField(f'ScanID:[{sub_row.ScanID}] Conflict error. '
                                                                       'The [run] index value must be unique '
                                                                       'among the scans with the same modality.')
                                        else:
                                            conflict_tested.append(fname)
                                        build_bids_json(dset, sub_row, fname, json_fname, slope=slope, offset=offset)
                                else:
                                    fname = f'{row.FileName}'
                                    build_bids_json(dset, row, fname, json_fname, slope=slope, offset=offset)
                                list_tested_fn.append(temp_fname)
                        print('...Done.')
            except FileNotValidError:
                pass
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
