"""
@author: Timothy Ho (UVA) 
"""
# -*- coding: utf-8 -*-
from operator import index
from ..lib.errors import *
from .. import BrukerLoader, __version__
from ..lib.utils import set_rescale, save_meta_files, mkdir
from ..lib.recon import recon
import argparse
import os, re
import sys

import numpy as np
import nibabel as nib

_supporting_bids_ver = '1.2.2'


def main():
    parser = argparse.ArgumentParser(prog='brkrecon',
                                     description="Brkrecon command-line interface")
    parser.add_argument("-v", "--version", action='version', version='%(prog)s v{}'.format(__version__))
    

    input_str = "input raw Bruker data"
    output_dir_str = "output directory name"

    subparsers = parser.add_subparsers(title='Sub-commands',
                                       description='To run this command, you must specify one of the functions listed'
                                                   'below next to the command. For more information on each function, '
                                                   'use -h next to the function name to call help document.',
                                       help='description',
                                       dest='function',
                                       metavar='command')
    test = subparsers.add_parser("test", help='Run test mode')
    test.add_argument("-i", "--input", help=input_str, type=str, default=None)
    test.add_argument("-o", "--output", help=output_dir_str, type=str, default=None)

    args = parser.parse_args()

    if args.function == 'test':
        ipath = args.input
        study    = BrukerLoader(ipath)
        print(ipath)
        
        if study.is_pvdataset:
            
            output = '{}_{}'.format(study._pvobj.subj_id,study._pvobj.study_id)
            mkdir(output)
            for id in study._avail.keys():
                fid_binary = study.get_fid(id)
                acqp = study.get_acqp(id)
                meth = study.get_method(id)
                reco = study._pvobj.get_reco(id, 1)
                process = 'image'
                data = recon(fid_binary, acqp, meth, reco, process=process)
                
                # Check if Image recontructed
                if len(data.shape) > 3:
                    output_fname =f"{acqp._parameters['ACQ_scan_name'].strip().replace(' ','_')}"
                    for c in range(data.shape[4]):
                        ni_img  = nib.Nifti1Image(np.abs(np.squeeze(data)), affine=np.eye(4))
                        nib.save(ni_img, os.path.join(output,f"{acqp._parameters['ACQ_scan_name'].strip().replace(' ','_')}_C{c}.nii.gz"))
                    print('NifTi file is generated... [{}]'.format(output_fname))
        else:
            print('{} is not PvDataset.'.format(ipath))

        
if __name__ == '__main__':
    main()