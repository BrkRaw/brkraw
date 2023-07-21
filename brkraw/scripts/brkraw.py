# -*- coding: utf-8 -*-
from operator import index
from ..lib.errors import *
from .. import BrukerLoader, __version__
from ..lib.utils import set_rescale, save_meta_files, mkdir
import argparse
import os, re
import sys

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

    # Adding arguments for each parser
    # gui
    gui.add_argument("-i", "--input", help=input_str, type=str, default=None)
    gui.add_argument("-o", "--output", help=output_dir_str, type=str, default=None)
    gui.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    gui.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    gui.add_argument("--ignore-rescale", help='remove slope and offset values from header', action='store_true')

    # tonii
    nii.add_argument("input", help=input_str, type=str)
    nii.add_argument("-b", "--bids", help=bids_opt, action='store_true')
    nii.add_argument("-o", "--output", help=output_fnm_str, type=str, default=False)
    nii.add_argument("-s", "--scanid", help="Scan ID, option to specify a particular scan to convert.", type=str)
    nii.add_argument("-r", "--recoid", help="RECO ID (default=1), "
                                            "option to specify a particular reconstruction id to convert",
                     type=int, default=1)
    nii.add_argument("-t", "--subjecttype", help="override subject type in case the original setting was not properly set." + \
                     "available options are (Biped, Quadruped, Phantom, Other, OtherAnimal)", type=str, default=None)
    nii.add_argument("-p", "--position", help="override position information in case the original setting was not properly input." + \
                     "the position variable can be defiend as <BodyPart>_<Side>, " + \
                     "available BodyParts are (Head, Foot, Tail) and sides are (Supine, Prone, Left, Right). (e.g. Head_Supine)", type=str, default=None)
    nii.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    nii.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    nii.add_argument("--ignore-rescale", help='remove slope and offset values from header', action='store_true')
    nii.add_argument("--ignore-localizer", help='ignore the scan if it is localizer', action='store_true', default=True)

    # tonii_all
    niiall.add_argument("input", help=input_dir_str, type=str)
    niiall.add_argument("-o", "--output", help=output_dir_str, type=str)
    niiall.add_argument("-b", "--bids", help=bids_opt, action='store_true')
    niiall.add_argument("-t", "--subjecttype", help="override subject type in case the original setting was not properly set." + \
                     "available options are (Biped, Quadruped, Phantom, Other, OtherAnimal)", type=str, default=None)
    niiall.add_argument("-p", "--position", help="override position information in case the original setting was not properly input." + \
                     "the position variable can be defiend as <BodyPart>_<Side>, " + \
                     "available BodyParts are (Head, Foot, Tail) and sides are (Supine, Prone, Left, Right). (e.g. Head_Supine)", type=str, default=None)
    niiall.add_argument("--ignore-slope", help='remove slope value from header', action='store_true')
    niiall.add_argument("--ignore-offset", help='remove offset value from header', action='store_true')
    niiall.add_argument("--ignore-rescale", help='remove slope and offset values from header', action='store_true')
    niiall.add_argument("--ignore-localizer", help='ignore the scan if it is localizer', action='store_true')

    # bids_helper
    bids_helper.add_argument("input", help=input_dir_str, type=str)
    bids_helper.add_argument("output", help="output BIDS datasheet filename", type=str) # [220202] make compatible with csv, tsv and xlsx
    bids_helper.add_argument("-f", "--format", help="file format of BIDS dataheets. Use this option if you did not specify the extension on output. The available options are (csv/tsv/xlsx) (default: csv)", type=str, default='csv')
    bids_helper.add_argument("-j", "--json", help="create JSON syntax template for "
                                                  "parsing metadata from the header", action='store_true')
    bids_helper.add_argument("-s", "--subj", help="switch subject and study IDs", action='store_true')
    bids_helper.add_argument("-t", "--sess", help="switch session and study ID", action='store_true')

    # bids_convert
    bids_convert.add_argument("input", help=input_dir_str, type=str)
    bids_convert.add_argument("datasheet", help="input BIDS datahseet filename", type=str)
    bids_convert.add_argument("-j", "--json", help="input JSON syntax template filename", type=str, default=False)
    bids_convert.add_argument("-o", "--output", help=output_dir_str, type=str, default=False)
    bids_convert.add_argument("-t", "--subjecttype", help="override subject type in case the original setting was not properly set." + \
                     "available options are (Biped, Quadruped, Phantom, Other, OtherAnimal)", type=str, default=None)
    bids_convert.add_argument("-p", "--position", help="override position information in case the original setting was not properly input." + \
                     "the position variable can be defiend as <BodyPart>_<Side>, " + \
                     "available BodyParts are (Head, Foot, Tail) and sides are (Supine, Prone, Left, Right). (e.g. Head_Supine)", type=str, default=None)
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
        path     = args.input
        scan_id  = args.scanid
        reco_id  = args.recoid
        study    = BrukerLoader(path)
        slope, offset = set_rescale(args)
        ignore_localizer = args.ignore_localizer
        study = override_header(study, args.subjecttype, args.position)
        
        if study.is_pvdataset:
            if args.output:
                output = args.output
            else:
                output = '{}_{}'.format(study._pvobj.subj_id,study._pvobj.study_id)
            if scan_id:
                acqpars  = study.get_acqp(int(scan_id))
                scanname = acqpars._parameters['ACQ_scan_name']
                scanname = scanname.replace(' ','-')
                output_fname = '{}-{}-{}-{}'.format(output, scan_id, reco_id, scanname)
                scan_id = int(scan_id)
                reco_id = int(reco_id)
                
                if ignore_localizer and is_localizer(study, scan_id, reco_id):
                    print('Identified a localizer, the file will not be converted: ScanID:{}'.format(str(scan_id)))
                else:
                    try:
                        study.save_as(scan_id, reco_id, output_fname, slope=slope, offset=offset)
                        save_meta_files(study, args, scan_id, reco_id, output_fname)
                        print('NifTi file is generated... [{}]'.format(output_fname))
                    except:
                        print('Conversion failed: ScanID:{}, RecoID:{}'.format(str(scan_id), str(reco_id)))
            else:
                for scan_id, recos in study._pvobj.avail_reco_id.items():
                    acqpars  = study.get_acqp(int(scan_id))
                    scanname = acqpars._parameters['ACQ_scan_name']
                    scanname = scanname.replace(' ','-')
                    if ignore_localizer and is_localizer(study, scan_id, recos[0]):
                        print('Identified a localizer, the file will not be converted: ScanID:{}'.format(str(scan_id)))
                    else:
                        for reco_id in recos:
                            output_fname = '{}-{}-{}-{}'.format(output, str(scan_id).zfill(2), reco_id, scanname)
                            try:
                                study.save_as(scan_id, reco_id, output_fname, slope=slope, offset=offset)
                                save_meta_files(study, args, scan_id, reco_id, output_fname)
                                print('NifTi file is generated... [{}]'.format(output_fname))
                            except:
                                print('Conversion failed: ScanID:{}, RecoID:{}'.format(str(scan_id), str(reco_id)))
        else:
            print('{} is not PvDataset.'.format(path))

    elif args.function == 'tonii_all':
        from os.path import join as opj, isdir, isfile

        path = args.input
        slope, offset = set_rescale(args)
        ignore_localizer = args.ignore_localizer
        invalid_error_message = '[Error] Invalid input path: {}\n'.format(path)
        empty_folder = '        The input path does not contain any raw data.'
        wrong_target = '        The input path indicates raw data itself. \n' \
                       '        You must input the parents folder instead of path of the raw data\n' \
                       '        If you want to convert single session raw data, use (tonii) instead.'

        list_of_raw = sorted([d for d in os.listdir(path) if isdir(opj(path, d)) \
                              or (isfile(opj(path, d)) and (('zip' in d) or ('PvDataset' in d)))])
        if not len(list_of_raw):
            # raise error with message if the folder is empty (or does not contains any PvDataset)
            print(invalid_error_message, empty_folder)
            raise InvalidApproach(invalid_error_message)
        if BrukerLoader(path).is_pvdataset:
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
                study = override_header(study, args.subjecttype, args.position)
                if len(study._pvobj.avail_scan_id):
                    subj_path = os.path.join(base_path, 'sub-{}'.format(study._pvobj.subj_id))
                    mkdir(subj_path)
                    sess_path = os.path.join(subj_path, 'ses-{}'.format(study._pvobj.study_id))
                    mkdir(sess_path)
                    for scan_id, recos in study._pvobj.avail_reco_id.items():
                        if ignore_localizer and is_localizer(study, scan_id, recos[0]): # add option to exclude localizer during mass conversion
                            print('Identified a localizer, the file will not be converted: ScanID:{}'.format(str(scan_id)))
                        else:
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
                                    print('Conversion failed: ScanID:{}, RecoID:{}'.format(str(scan_id), str(reco_id)))
                    print('{} is converted...'.format(raw))
                else:
                    print('{} does not contains any scan data to convert...'.format(raw))
            else:
                print('{} is not PvDataset.'.format(raw))

    elif args.function == 'bids_helper':
        import pandas as pd
        import warnings
        path = os.path.abspath(args.input)
        ds_output = os.path.abspath(args.output)
        make_json = args.json
        swap_id = args.subj
        swap_sess = args.sess

        if swap_id and swap_sess:
            warnings.warn('\nBoth switch subject/study IDs and switch session/study ID options are on. You probably do not want this!\n')

        # [220202] for back compatibility
        ds_fname, ds_output_ext = os.path.splitext(ds_output)
        if ds_output_ext in ['.xlsx', '.csv', '.tsv']:
            ds_format = ds_output_ext[1:]
        else:
            ds_format = args.format

        # [220202] make compatible with csv, tsv and xlsx
        output = '{}.{}'.format(ds_fname, ds_format) 

        Headers = ['RawData', 'SubjID', 'SessID', 'ScanID', 'RecoID', 'DataType',
                   'task', 'acq', 'ce', 'rec', 'dir', 'run', 'flip', 'mt', 'part', 'modality', 'Start', 'End']
        df = pd.DataFrame(columns=Headers)

        # if the path directly contains scan files for one participant
        if 'subject' in os.listdir(path):
            dNames = ['']
        else:         # old way, when you run against the parent folder (which contains one or more scan folder).
            dNames = sorted(os.listdir(path))

        for dname in dNames:
            dpath = os.path.join(path, dname)

            try:
                dset = BrukerLoader(dpath)
            except:
                dset = None

            if dset != None:
                if dset.is_pvdataset:
                    pvobj = dset.pvobj

                    rawdata = pvobj.path
                    
                    if swap_id:
                        subj_id = pvobj.study_id
                    else:
                        subj_id = pvobj.subj_id

                    if swap_sess:
                        sess_id = pvobj.study_id
                    else:
                        sess_id = pvobj.session_id

                    # make subj_id bids appropriate
                    subj_id = cleanSubjectID(subj_id)

                    # make sess_id bids appropriate
                    sess_id = cleanSessionID(sess_id)

                    for scan_id, recos in pvobj.avail_reco_id.items():
                        for reco_id in recos:
                            visu_pars = dset.get_visu_pars(scan_id, reco_id)
                            if dset._get_dim_info(visu_pars)[1] == 'spatial_only':
                                
                                if not is_localizer(dset, scan_id, reco_id):
                                    method = dset.get_method(scan_id).parameters['Method']

                                    datatype = assignDataType(method)

                                    item = dict(zip(Headers, [rawdata, subj_id, sess_id, scan_id, reco_id, datatype]))
                                    if datatype == 'fmap':
                                        for m, s, e in [['fieldmap', 0, 1], ['magnitude', 1, 2]]:
                                            item['modality'] = m
                                            item['Start'] = s
                                            item['End'] = e
                                            df = pd.concat([df, pd.DataFrame([item])], ignore_index=True)
                                    elif datatype == 'dwi':
                                        item['modality'] = 'dwi'
                                        df = pd.concat([df, pd.DataFrame([item])], ignore_index=True)
                                    elif datatype == 'anat' and re.search('MSME', method, re.IGNORECASE):
                                        item['modality'] = 'MESE'
                                        df = pd.concat([df, pd.DataFrame([item])], ignore_index=True)
                                    else:
                                        df = pd.concat([df, pd.DataFrame([item])], ignore_index=True)
        if 'xlsx' in ds_format:
            df.to_excel(output, index=None)
        elif 'csv' in ds_format:
            df.to_csv(output, index=None, sep=',')
        elif 'tsv' in ds_format:
            df.to_csv(output, index=None, sep='\t')
        else:
            print('[{}] is not supported.'.format(ds_format))
            raise InvalidApproach('Invalid input for datasheet!')

        if make_json:
            json_fname = '{}.json'.format(ds_fname)
            print('Creating JSON syntax template for parsing the BIDS required metadata '
                  '(BIDS v{}): {}'.format(_supporting_bids_ver, json_fname))
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
        from ..lib.utils import build_bids_json, bids_validation
        
        pd.options.mode.chained_assignment = None
        path = args.input
        datasheet = args.datasheet
        output = args.output
        datasheet_ext = os.path.splitext(datasheet)[-1]

        # [220202] make compatible with csv, tsv and xlsx
        if 'xlsx' in datasheet_ext:
            df = pd.read_excel(datasheet, dtype={'SubjID': str, 'SessID': str, 'run': str})
        elif 'csv' in datasheet_ext:
            df = pd.read_csv(datasheet, dtype={'SubjID': str, 'SessID': str, 'run': str}, index_col=None, header=0, sep=',')
        elif 'tsv' in datasheet_ext:
            df = pd.read_csv(datasheet, dtype={'SubjID': str, 'SessID': str, 'run': str}, index_col=None, header=0, sep='\t')
        else:
            print(f'{datasheet_ext} if not supported format.')
            raise InvalidApproach('Invalid input for datasheet!')
            
        json_fname = args.json
        slope, offset = set_rescale(args)

        # check if the project is session included
        if all(pd.isnull(df['SessID'])):
            # SessID was removed (not column, but value), this need to go to documentation
            include_session = False
        else:
            # if SessionID appears in datasheet, then by default session appears.
            include_session = True

        if not output:
            root_path = os.path.abspath(os.path.join(os.path.curdir, 'Data'))
        else:
            root_path = output

        mkdir(root_path)

        # prepare the required file for converted BIDS dataset
        generateModalityAgnosticFiles(root_path, json_fname)

        print('Inspect input BIDS datasheet...')

        # if the path directly contains scan files for one participant
        if 'subject' in os.listdir(path):
            dNames = ['']
        else:         # old way, when you run against the parent folder (which contains one or more scan folder).
            dNames = sorted(os.listdir(path))

        for dname in dNames:
            dpath = os.path.join(path, dname)
            try:
                dset = BrukerLoader(dpath)
                dset = override_header(dset, args.subjecttype, args.position)
                if dset.is_pvdataset:
                    pvobj = dset.pvobj
                    rawdata = pvobj.path
                    filtered_dset = df[df['RawData'].isin([rawdata])].reset_index()

                    # add Filename and Dir colomn
                    filtered_dset.loc[:, 'FileName'] = [np.nan] * len(filtered_dset)
                    filtered_dset.loc[:, 'Dir'] = [np.nan] * len(filtered_dset)

                    if len(filtered_dset):
                        subj_id = list(set(filtered_dset['SubjID']))[0]
                        subj_code = 'sub-{}'.format(subj_id)
                        # append to participants.tsv one record
                        with open(os.path.join(root_path, 'participants.tsv'), 'a+') as f:
                            f.write(subj_code + '\n')

                        filtered_dset = completeFieldsCreateFolders(df, filtered_dset, dset, include_session, root_path, subj_code)

                        list_tested_fn = []
                        # Converting data according to the updated sheet
                        print('Converting {}...'.format(dname))

                        for i, row in filtered_dset.iterrows():
                            temp_fname = '{}_{}'.format(row.FileName, row.modality)
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
                                            fname = '{}_run-{}'.format(sub_row.FileName, str(j+1).zfill(2))
                                        else:
                                            _ = bids_validation(df, i, 'run', sub_row.run, 3, dtype=int)
                                            fname = '{}_run-{}'.format(sub_row.FileName, str(sub_row.run).zfill(2)) # [20210822] format error
                                        if fname in conflict_tested:
                                            raise ValueConflictInField('ScanID:[{}] Conflict error. '
                                                                       'The [run] index value must be unique '
                                                                       'among the scans with the same modality.'
                                                                       ''.format(sub_row.ScanID))
                                        else:
                                            conflict_tested.append(fname)
                                        build_bids_json(dset, sub_row, fname, json_fname, slope=slope, offset=offset)
                                else:
                                    fname = '{}'.format(row.FileName)
                                    build_bids_json(dset, row, fname, json_fname, slope=slope, offset=offset)
                                list_tested_fn.append(temp_fname)
                        print('...Done.')
            except FileNotValidError:
                pass
    else:
        parser.print_help()


def cleanSubjectID(subj_id):
    """To replace the underscore in subject id.
    Args:
        subj_id (str): the orignal subject id.
    Returns:
        str: the replaced subject id.
    """

    import warnings

    subj_id = str(subj_id)
    
    # underscore will mess up bids output
    if '_' in subj_id:
        subj_id = subj_id.replace('_', 'Underscore')
        # warn user that the subject/participantID has a '_' and is replaced with 'Underscore'
        warnings.warn('Participant or subject ID has "_"s, replaced with "Underscore" to make it bids compatiable. You should avoid use "_" in participant/subject ID for BIDS purpose')

    # Hyphen will mess up bids output
    if '-' in subj_id:
        subj_id = subj_id.replace('-', 'Hyphen')
        # warn user that the subject/participantID has a '-' and is replaced with 'Hyphen'
        warnings.warn('Participant or subject ID has "-"s, replaced with "Hyphen" to make it bids compatiable. You should avoid use "-" in participant/subject ID for BIDS purpose')
    return subj_id


# This could integrate with cleanSubjectID, but mind the different warning messages
def cleanSessionID(sess_id):
    """To replace the underscore in session id.
    Args:
        sess_id (str): the orignal session id.
    Returns:
        str: the replaced session id.
    """

    import warnings
    
    sess_id = str(sess_id)

    # underscore will mess up bids output
    if '_' in sess_id:
        sess_id = sess_id.replace('_', 'Underscore')
        # warn user that the subject/participantID has a '_' and is replaced with 'Underscore'
        warnings.warn('Session ID has "_"s, replaced with "Underscore" to make it bids compatiable. You should avoid use "_" in session ID for BIDS purpose')

    # Hyphen will mess up bids output
    if '-' in sess_id:
        sess_id = sess_id.replace('-', 'Hyphen')
        # warn user that the subject/participantID has a '-' and is replaced with 'Hyphen'
        warnings.warn('Session ID has "-"s, replaced with "Hyphen" to make it bids compatiable. You should avoid use "-" in session ID for BIDS purpose')

    return sess_id


def assignDataType (method):
    """To assign the dataType based on method.
    Args:
        method (str): the method from BrukerLoader.get_method.parameters['Method'].
    Returns:
        str: the datatype.
    """
    if re.search('epi', method, re.IGNORECASE) and not re.search('dti', method, re.IGNORECASE):
        #Why epi is function here? there should at lease a comment.
        datatype = 'func'
    elif re.search('dti', method, re.IGNORECASE):
        datatype = 'dwi'
    elif re.search('flash', method, re.IGNORECASE) or re.search('rare', method, re.IGNORECASE):
        datatype = 'anat'
    elif re.search('fieldmap', method, re.IGNORECASE):
        datatype = 'fmap'
    elif re.search('MSME', method, re.IGNORECASE):
        datatype = 'anat'

        # warn user for MSME default to anat and MESE
        import warnings
        msg = "MSME found in your scan, default to anat DataType and MESE modality, " + \
        "please update the datasheet to indicate the proper DataType if different than default." 
        warnings.warn(msg)

    else:
        # what is this? seems like holding files not able to identify
        datatype = 'etc'

        # warn user to manually update the DataType in datasheet
        import warnings
        
        msg = "\n \n ----- Important ----- \
        \n We do not know how to classify some of your scan and marked them as etc.\
        \n To produce valid BIDS outputs, please update the datasheet to indicate the proper DataType for them \n"
        warnings.warn(msg)

    return datatype


def generateModalityAgnosticFiles(root_path, json_fname):
    """To create ModalityAgnosticFiles in output folder.
    Args:
        root_path (str): the root output folder
        json_fname (str): I do not under why this variable is needed.
    Returns:
        nothing: just generate files.
    """
    data_des = 'dataset_description.json'
    readme = 'README'
    # why open use only the current folder and os.path not?
    if not os.path.exists(data_des):
        with open(os.path.join(root_path, 'dataset_description.json'), 'w') as f:
            import json
            import datetime
            from ..lib.reference import DATASET_DESC_REF
            json.dump(DATASET_DESC_REF, f, indent=4)
    if not os.path.exists(readme):
        with open(os.path.join(root_path, readme), 'w') as f:
            # I do not know why json_fname here.
            f.write('This dataset has been converted using BrkRaw (v{})'
                    'at {}.\n'.format(json_fname, datetime.datetime.now()))
            f.write('## How to cite?\n - https://doi.org/10.5281/zenodo.3818615\n')
    
    # https://bids-specification.readthedocs.io/en/stable/03-modality-agnostic-files.html
    # participant.tsv file. if not exist, create it, and append. if need tab use \t
    participantsTsvPath = os.path.join(root_path, 'participants.tsv')
    if not os.path.exists(participantsTsvPath):
        with open(participantsTsvPath, 'a+') as f:
            f.write('participant_id\n')
    else:
        print('Exiting before convert..., participants.tsv already exist in output folder: ', participantsTsvPath)
        sys.exit()

    # participant.json file. if not exist, create it, and append. if need tab use \t
    participantsJsonPath = os.path.join(root_path, 'participants.json')
    if not os.path.exists(participantsJsonPath):
        with open(participantsJsonPath, 'a+') as f:
            sideCar = { 
                "participant_id": {
                    "Description": "Participant identifier"
                }
            }
            json.dump(sideCar, f, indent=4)
    else:
        print('Exiting...before convert, participants.json already exist in output folder: ', participantsJsonPath)
        sys.exit()



def createFolderTree(include_session, row, root_path, subj_code):
    """To create participant (and session if include_session) folder.
    Args:
        include_session (bool): include_session.
        row (obj): a (panadas) row of data containing SessID and DataType.
        root_path (str): the root path of output folder
        subj_code (str): subject or participant folder name
    Returns:
        list: first 0 element is dtype_path, second 1 is fname.
    """
    if include_session:
        # If session included, make session dir
        sess_code = 'ses-{}'.format(row.SessID)
        subj_path = os.path.join(root_path, subj_code)
        mkdir(subj_path)
        subj_path = os.path.join(subj_path, sess_code)
        mkdir(subj_path)
        # add session info to filename as well
        fname = '{}_{}'.format(subj_code, sess_code)
    else:
        subj_path = os.path.join(root_path, subj_code)
        mkdir(subj_path)
        fname = '{}'.format(subj_code)
    
    datatype = row.DataType
    dtype_path = os.path.join(subj_path, datatype)
    mkdir(dtype_path)

    return [dtype_path, fname]


def completeFieldsCreateFolders (df, filtered_dset, dset, multi_session, root_path, subj_code):
    """To complete the dataframe fields and create output folders. [too many parameters]
    Args:
        df (dataframe): original pandas dataframe, not sure whether it can replaced by filtered_dset (someone has to figure it out)
        filtered_dset (dataframe): filtered pandas dataframe
        dset (object): BrukerLoader(dpath) object
        multi_session (bool): multi_session.
        root_path (str): the root path of output folder
        subj_code (str): subject or participant folder name
    Returns:
        dataframe: the completed filtered_dset.
    """
    import pandas as pd
    from ..lib.utils import bids_validation

    # iterrows to create folder tree, add to filtered_dset fname, dtype_path, and modality
    for i, row in filtered_dset.iterrows():
        dtype_path, fname = createFolderTree(multi_session, row, root_path, subj_code)
        if pd.notnull(row.task):
            if bids_validation(df, i, 'task', row.task, 10):
                fname = '{}_task-{}'.format(fname, row.task)
        if pd.notnull(row.acq):
            if bids_validation(df, i, 'acq', row.acq, 10):
                fname = '{}_acq-{}'.format(fname, row.acq)
        if pd.notnull(row.ce):
            if bids_validation(df, i, 'ce', row.ce, 5):
                fname = '{}_ce-{}'.format(fname, row.ce)
        if pd.notnull(row.dir):
            if bids_validation(df, i, 'dir', row.dir, 2):
                fname = '{}_dir-{}'.format(fname, row.dir)
        if pd.notnull(row.rec):
            if bids_validation(df, i, 'rec', row.rec, 2):
                fname = '{}_rec-{}'.format(fname, row.rec)
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
    
    return filtered_dset


def is_localizer(pvobj, scan_id, reco_id):
    visu_pars = pvobj.get_visu_pars(scan_id, reco_id)
    if 'VisuAcquisitionProtocol' in visu_pars.parameters:
        ac_proc = visu_pars.parameters['VisuAcquisitionProtocol']
        if re.search('tripilot', ac_proc, re.IGNORECASE) or re.search('localizer', ac_proc, re.IGNORECASE):
            return True
        else:
            return False
    else:
        return False


def override_header(pvobj, subjtype, position):
    """override subject position and subject type"""
    import warnings
    if position != None:
        try:
            pvobj.override_position(position)
        except:
            msg = "Unknown position string [{}]. Please check your input option.".format(position) + \
                  "The position variable can be defiend as <BodyPart>_<Side>," + \
                  "available BodyParts are (Head, Foot, Tail) and sides are (Supine, Prone, Left, Right). (e.g. Head_Supine)"
            raise InvalidApproach(msg)
    if subjtype != None:
        try:
            pvobj.override_subjtype(subjtype)
        except:
            msg = "Unknown subject type [{}]. Please check your input option.".format(subjtype) + \
                  "available options are (Biped, Quadruped, Phantom, Other, OtherAnimal)"
            raise InvalidApproach(msg)
    return pvobj


if __name__ == '__main__':
    main()
