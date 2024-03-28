"""
 DEVELOPED FOR BRUKER PARAVISION 7 datasets
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
from brkraw.lib.pvobj  import PvDatasetDir
from brkraw.lib.utils  import get_value, mkdir
import brkraw as br
from brkraw.lib.recon import *

import nibabel as nib
import sigpy as sp

PV_zipfile = '/home/jac/data/external_data/20231128_132106_hluna_piloFe_irm4_rata26_hluna_piloFe_irm4__1_1'
data_loader = br.load(PV_zipfile)

ExpNum = 6 
for ExpNum in data_loader._avail.keys():
    # Raw data processing for single job
    fid_binary = data_loader.get_fid(ExpNum)
    acqp = data_loader.get_acqp(ExpNum)
    meth = data_loader.get_method(ExpNum)
    reco = data_loader._pvobj.get_reco(ExpNum, 1)
    print(get_value(acqp, 'ACQ_sw_version'))
    print(get_value(acqp, 'ACQ_protocol_name' ), ExpNum)
    print(get_value(acqp, 'ACQ_size' ))
    """
    # test functions
    dt_code = np.dtype('int32') 
    bits = 32 # Follows dtype
    dt_code = dt_code.newbyteorder('<')
    fid = np.frombuffer(fid_binary, dt_code)

    NI = get_value(acqp, 'NI')
    NR = get_value(acqp, 'NR')
    nRecs = 1 # THIS NEEDS TO BE EXAMINED BUT IDK HOW
    ACQ_size = get_value(acqp, 'ACQ_size' )

    if get_value(acqp, 'GO_block_size') == 'Standard_KBlock_Format':
        blocksize = int(np.ceil(ACQ_size[0]*nRecs*(bits/8)/1024)*1024/(bits/8))
    else:
        blocksize = int(ACQ_size[0]*nRecs)

    # CHECK SIZE
    print(fid.size, blocksize*np.prod(ACQ_size[1:])*NI*NR)
    if fid.size != blocksize*np.prod(ACQ_size[1:])*NI*NR:
        print('Error Size dont match')

    # Reshape
    fid = fid[::2] + 1j*fid[1::2] 
    fid = fid.reshape([-1,blocksize//2])

    # THIS REMOVES ZERO FILL (IDK THE PURPOSE FOR THIS)
    if blocksize != ACQ_size[0]*nRecs:
        fid = fid[:,:ACQ_size[0]//2]
        fid = fid.reshape((-1,ACQ_size[0]//2, nRecs))
        fid = fid.transpose(0,2,1)
        
    else:
        #UNTESTED TIM FEB 12 2024 (IDK WHAT THIS DOES)
        fid = fid.reshape((ACQ_size[0]//2, nRecs, -1))
        

    print(fid.shape)
    frame = convertRawToFrame(fid, acqp, meth)
    print(frame.shape)
    #image = sp.ifft(np.squeeze(frame), axes=[0,1])
    CKdata = convertFrameToCKData(frame,acqp, meth)
    print(CKdata.shape)
    process = 'image' 
        
    # test functions
    data = brkraw_Reco(CKdata, deepcopy(reco), meth, recoparts = 'default')
    """
    # -----------------------------------------------------------------
    data = recon(fid_binary, acqp, meth, reco, recoparts='default')
    print(data.shape)
    
    if len(data.shape) == 7:
        output = '{}_{}'.format(data_loader._pvobj.subj_id,data_loader._pvobj.study_id)
        mkdir(output)
        output_fname =f"{acqp._parameters['ACQ_scan_name'].strip().replace(' ','_')}"
        for c in range(data.shape[4]):
            ni_img  = nib.Nifti1Image(np.angle(np.squeeze(data[:,:,:,:,c,:,:])), affine=np.eye(4))
            nib.save(ni_img, os.path.join(output,f"{acqp._parameters['ACQ_scan_name'].strip().replace(' ','_')}_C{c}.nii.gz"))
        print('NifTi file is generated... [{}]'.format(output_fname))
           