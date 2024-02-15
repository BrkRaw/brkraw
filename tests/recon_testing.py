"""
 DEVELOPED FOR BRUKER PARAVISION 360 datasets
 Below code will work for cartesian sequence
 GRE, MSME, RARE that were acquired with linear
 phase encoding

@author: Tim Ho (UVA) 
"""

import os
import time

import numpy as np
import matplotlib.pyplot as plt 

import brkraw as br
from brkraw.lib.parser import Parameter
from brkraw.lib.pvobj import PvDatasetDir
from brkraw.lib.utils import get_value, mkdir
import brkraw as br
from brkraw.lib.recon import recon

import nibabel as nib


#PV_zipfile = "/home/jac/data/PV36034results20230630/Wilson_Tim_26171_1_Default_RAREvfl_26174_360.3.4.PvDatasets"
PV_zipfile = "/home/jac/data/nmrsu_data/Tim_Wilson_Tim_207023_1_Default_20231202FeCl3_210800_360.3.4.PvDatasets"
data_loader = br.load(PV_zipfile)

for ExpNum in data_loader._avail.keys():
    # Raw data processing for single job
    fid_binary = data_loader.get_fid(ExpNum)
    acqp = data_loader.get_acqp(ExpNum)
    meth = data_loader.get_method(ExpNum)
    reco = data_loader._pvobj.get_reco(ExpNum, 1)
    
    print(get_value(acqp, 'ACQ_protocol_name' ), ExpNum)
    print(get_value(acqp, 'ACQ_ScanPipeJobSettings' ), ExpNum)
    
    # process OPTIONS: 'raw', 'frame', 'CKdata', 'image'    
    process = 'image' 
    
    # test functions
    start_time = time.time()
    data = recon(fid_binary, acqp, meth, reco, process=process)
    print("{} convert {} seconds".format (process, time.time()-start_time))
    data = data/np.max(np.abs(data)) # Normalize Data
    # Check if Image recontructed
    output = '{}_{}'.format(data_loader._pvobj.subj_id,data_loader._pvobj.study_id)
    mkdir(output)

    # Reconstructed Image Matrix is always 7-dimensional
    #[x,y,z,_,n_channel,NI,NR]
    if len(data.shape) == 7:
        print(data.shape)
        output_fname =f"{acqp._parameters['ACQ_scan_name'].strip().replace(' ','_')}"
    
        for c in range(data.shape[4]):
            ni_img  = nib.Nifti1Image(np.abs(np.squeeze(data[:,:,:,:,c,:,:])), affine=np.eye(4))
            nib.save(ni_img, os.path.join(output,f"{acqp._parameters['ACQ_scan_name'].strip().replace(' ','_')}_C{c}.nii.gz"))
        print('NifTi file is generated... [{}]'.format(output_fname))
        