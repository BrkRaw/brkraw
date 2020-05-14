# -*- coding: utf-8 -*-
from shleeh import *
from shleeh.errors import *
from .. import BrukerLoader, __version__
import argparse
import os, re


def mkdir(path):
    try:
        os.stat(path)
    except FileNotFoundError or OSError:
        os.mkdir(path)
    except:
        raise UnexpectedError


def main():
    parser = argparse.ArgumentParser(prog='brkraw.py',
                                     description="Command line tool of Bruker Rawdata Handler")
    parser.add_argument("-v", "--version", action='version', version='%(prog)s v{}'.format(__version__))

    subparsers = parser.add_subparsers(title='Sub-commands',
                                       description='brkraw.py provides two major function reporting '
                                                   'contents on bruker raw data '
                                                   'and converting image data into NifTi format.',
                                       help='description',
                                       dest='function',
                                       metavar='command')

    summary = subparsers.add_parser("summary", help='Print out data summary')
    summary.add_argument("input", help="The source path for single Bruker raw data", type=str)

    gui = subparsers.add_parser("gui", help='Start GUI')
    gui.add_argument("-i", "--input", help="The source path for single Bruker raw data", type=str, default=None)
    gui.add_argument("-o", "--output", help="The destination path for converted NifTi data", type=str, default=None)

    nii = subparsers.add_parser("tonii", help='Convert to NifTi format')
    nii.add_argument("input", help="The source path for single Bruker raw data", type=str)
    nii.add_argument("-b", "--bids", help="Create JSON file with BIDS "
                                          "standard MRI acquisition parameter.", action='store_true')
    nii.add_argument("-o", "--output", help="Filename w/o extension to export NifTi image", type=str, default=False)
    nii.add_argument("-r", "--recoid", help="RECO ID (if scan_id has multiple reconstruction data)", type=int, default=1)
    nii.add_argument("-s", "--scanid", help="Scan ID", type=str)

    niiall = subparsers.add_parser("tonii_all", help="Convert All Bruker raw data.")
    niiall.add_argument("input", help="The source path that contains multiple Bruker raw data", type=str)
    niiall.add_argument("-b", "--bids", help="Create JSON file with BIDS standard MRI acquisition parameter.",
                        action='store_true')

    bids_list = subparsers.add_parser("bids_list", help="Generate BIDS datasheets (xlsx format)")
    bids_list.add_argument("input", help="The source path that contains multiple Bruker raw data", type=str)
    bids_list.add_argument("output", help='The destination path for BIDS datasheet', type=str)
    bids_list.add_argument("-r", "--meta_ref", help="the path for BIDS Metadata reference", type=str, default=False)

    bids_converter = subparsers.add_parser("bids_converter", help="Convert ALL Bruker raw data "
                                                                  "according to the BIDS datasheet")
    bids_converter.add_argument("input_raw", help="The source path that contains multiple Bruker raw data", type=str)
    bids_converter.add_argument("input_xlsx", help="The BIDS datasheet file", type=str)
    bids_converter.add_argument("-r", "--meta_ref", help="BIDS Metadata reference", type=str, default=False)

    args = parser.parse_args()

    if args.function == 'summary':
        path = args.input
        if any([os.path.isdir(path), ('zip' in path), ('PvDataset' in path)]):
            study = BrukerLoader(path)
            study.summary()
        else:
            list_path = [d for d in os.listdir('.') if (any([os.path.isdir(d),
                                                             ('zip' in d),
                                                             ('PvDataset' in d)]) and re.search(path, d, re.IGNORECASE))]
            for p in list_path:
                study = BrukerLoader(p)
                study.summary()

    elif args.function == 'gui':
        ipath = args.input
        opath = args.output
        from ..ui.main_win import MainWindow
        root = MainWindow()
        if ipath != None:
            root._path = ipath
            root._extend_layout()
            root._load_dataset()
        if opath != None:
            root._output = opath
        root.mainloop()

    elif args.function == 'tonii':
        path = args.input
        scan_id = args.scanid
        reco_id = args.recoid
        study = BrukerLoader(path)
        if args.output:
            output = args.output
        else:
            output = '{}_{}'.format(study._pvobj.subj_id,study._pvobj.study_id)
        if scan_id:
            output_fname = '{}-{}-{}'.format(output, scan_id, reco_id)
            try:
                study.save_as(scan_id, reco_id, output_fname)
                if args.bids:
                    study.save_json(scan_id, reco_id, output_fname)
                print('NifTi file is generated... [{}]'.format(output_fname))
            except Exception as e:
                print('[Warning]::{}'.format(e))
        else:
            for scan_id, recos in study._pvobj.avail_reco_id.items():
                for reco_id in recos:
                    output_fname = '{}-{}-{}'.format(output, str(scan_id).zfill(2), reco_id)
                    try:
                        study.save_as(scan_id, reco_id, output_fname)
                        if args.bids:
                            study.save_json(scan_id, reco_id, output_fname)
                        print('NifTi file is genetared... [{}]'.format(output_fname))
                    except Exception as e:
                        print('[Warning]::{}'.format(e))

    elif args.function == 'tonii_all':
        path = args.input
        from os.path import join as opj, isdir, isfile
        list_of_raw = sorted([d for d in os.listdir(path) if isdir(opj(path, d)) \
                              or (isfile(opj(path, d)) and (('zip' in d) or ('PvDataset' in d)))])
        base_path = 'Data'
        try:
            os.mkdir(base_path)
        except:
            pass
        for raw in list_of_raw:
            sub_path = os.path.join(path, raw)
            study = BrukerLoader(sub_path)
            if len(study._pvobj.avail_scan_id):
                subj_path = os.path.join(base_path, 'sub-{}'.format(study._pvobj.subj_id))
                try:
                    os.mkdir(subj_path)
                except OSError:
                    pass
                else:
                    raise UnexpectedError
                sess_path = os.path.join(subj_path, 'ses-{}'.format(study._pvobj.study_id))
                try:
                    os.mkdir(sess_path)
                except OSError:
                    pass
                else:
                    raise UnexpectedError
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
                    try:
                        os.mkdir(output_path)
                    except OSError:
                        pass
                    else:
                        raise UnexpectedError
                    filename = 'sub-{}_ses-{}_{}'.format(study._pvobj.subj_id, study._pvobj.study_id,
                                                         str(scan_id).zfill(2))
                    for reco_id in recos:
                        output_fname = os.path.join(output_path, '{}_reco-{}'.format(filename,
                                                                                     str(reco_id).zfill(2)))
                        try:
                            study.save_as(scan_id, reco_id, output_fname)
                            if args.bids:
                                study.save_json(scan_id, reco_id, output_fname)
                            if re.search('dti', method, re.IGNORECASE):
                                study.save_bdata(scan_id, reco_id, output_fname)
                        except Exception as e:
                            print(e)
                print(f'{raw} is converted...')
            else:
                print(f'{raw} is empty...')

    elif args.function == 'bids_list':
        import pandas as pd
        path = os.path.abspath(args.input)
        output = os.path.abspath(args.output)
        ref_path = args.meta_ref
        if not output.endswith('.xlsx'):
            # to prevent pandas ValueError in case user does not provide valid file extension.
            output = f'{output}.xlsx'

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
                                    else:
                                        df = df.append(item, ignore_index=True)
        df.to_excel(output, index=None)
        if ref_path:
        # ref_path = os.path.join(os.path.dirname(output), 'BIDS_META_REF.json')
            if not ref_path.endswith('json'):
                ref_path = f'{ref_path}.json'
            print(f'Creating BIDS metadata reference file (BIDS v1.2.2): {ref_path}')
            with open(ref_path, 'w') as f:
                import json
                from ..lib.reference import COMMON_META_REF, FMRI_META_REF, FIELDMAP_META_REF
                ref_dict = dict(common=COMMON_META_REF,
                                func=FMRI_META_REF,
                                fmap=FIELDMAP_META_REF)
                json.dump(ref_dict, f, indent=4)
        print('Please complete the exported BIDS datasheet [{}] '
              'according to BIDS standard guide.'.format(os.path.basename(output)))
        print('**This tool is just a utility to help minimize the effort for data organization, '
              'so it will not guarantee that the dataset can meet the requirement of the official BIDS validator.**')

    elif args.function == 'bids_converter':
        import pandas as pd
        import numpy as np
        import json
        import datetime
        from ..lib.utils import build_bids_json, bids_validation

        pd.options.mode.chained_assignment = None
        path = args.input_raw
        input_xlsx = args.input_xlsx
        df = pd.read_excel(input_xlsx, dtype={'SubjID': str, 'SessID': str, 'run': str})
        ref_path = args.meta_ref

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

        root_path = os.path.abspath(os.path.join(os.path.curdir, 'Data'))
        mkdir(root_path)
        data_des = 'dataset_description.json'
        readme = 'README'
        if not os.path.exists(data_des):
            with open(os.path.join(root_path, 'dataset_description.json'), 'w') as f:
                from ..lib.reference import DATASET_DESC_REF
                json.dump(DATASET_DESC_REF, f, indent=4)
        if not os.path.exists(readme):
            with open(os.path.join(root_path, readme), 'w') as f:
                f.write(f'This dataset has converted using BrkRaw (v{__version__}) at {datetime.datetime.now()}.\n')
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
                                        build_bids_json(dset, sub_row, fname, ref_path)
                                else:
                                    fname = f'{row.FileName}'
                                    build_bids_json(dset, row, fname, ref_path)
                                list_tested_fn.append(temp_fname)
                        print('...Done.')
            except FileNotValidError:
                pass
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
