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
from brkraw.lib.recon import *

import nibabel as nib
import sigpy as sp

PV_zipfile = '/home/jac/data/external_data/PV6/RARE_3D'
ExpNum = 35 
PV_zipfile = os.path.join(PV_zipfile,str(ExpNum))
#PV_zipfile = '/home/jac/data/external_data/PV6/RARE_3slice_packages/5'
# Raw data processing for single job
with open(os.path.join(PV_zipfile, 'method'), 'r') as f:
    meth = Parameter(f.read().split('\n'))
with open(os.path.join(PV_zipfile, 'acqp'), 'r') as f:
    acqp = Parameter(f.read().split('\n'))
print(os.path.join(PV_zipfile,'/pdata/1/reco'))
with open(os.path.join(PV_zipfile,'pdata/1','reco'), 'r') as f:
    reco = Parameter(f.read().split('\n'))

fid_path = os.path.join(PV_zipfile, 'fid')
print(fid_path)
if os.path.exists(fid_path):
    with open(fid_path, 'rb') as f:
        fid_binary = f.read()
else:
    fid_path = os.path.join(PV_zipfile, 'rawdata.job0') 
    with open(fid_path, 'rb') as f:
        fid_binary = f.read()
print(get_value(acqp, 'ACQ_sw_version'))
print(get_value(acqp, 'ACQ_protocol_name' ), ExpNum)

# test functions
dt_code = np.dtype('int32') 
bits = 32 # Follows dtype
dt_code = dt_code.newbyteorder('<')
fid = np.frombuffer(fid_binary, dt_code)
print(fid.shape)

NI = get_value(acqp, 'NI')
NR = get_value(acqp, 'NR')
nRecs = 2
#if get_value(acqp,'ACQ_ReceiverSelect') != None:
#    nRecs = get_value(acqp, 'ACQ_ReceiverSelect').count('Yes') # THIS NEEDS TO BE EXAMINED BUT IDK HOW
ACQ_size = get_value(acqp, 'ACQ_size' )

if get_value(acqp, 'GO_block_size') == 'Standard_KBlock_Format':
    blocksize = int(np.ceil(ACQ_size[0]*nRecs*(bits/8)/1024)*1024/(bits/8))
else:
    blocksize = int(ACQ_size[0]*nRecs)

# CHECK SIZE
print(fid.size, blocksize*np.prod(ACQ_size[1:])*NI*NR)
if fid.size != blocksize*np.prod(ACQ_size[1:])*NI*NR:
    print('Error size dont match')

# Reshape
fid = fid[::2] + 1j*fid[1::2] 
fid = fid.reshape([-1,blocksize//2])

print(blocksize, fid.shape)
print(ACQ_size)
# THIS REMOVES ZERO FILL (IDK THE PURPOSE FOR THIS)
if blocksize != ACQ_size[0]*nRecs:
    print('a')
    fid = fid[:,:ACQ_size[0]//2]
    fid = fid.reshape((-1,nRecs,ACQ_size[0]//2))
    fid = fid.transpose(0,1,2)
else:
    print('b')
    #UNTESTED TIM FEB 12 2024 (IDK WHAT THIS DOES)
    fid = fid.reshape((ACQ_size[0]//2, nRecs, -1))
    

print(fid.shape)
print('raw2frame')
frame = convertRawToFrame(fid, acqp, meth)
print(frame.shape)
#image = sp.ifft(np.squeeze(frame), axes=[0,1])
CKdata = convertFrameToCKData(frame,acqp, meth)

print(CKdata.shape)
process = 'image' 
    
# test functions
data = brkraw_Reco(CKdata, deepcopy(reco), meth, recoparts = 'default')
""""""
# -----------------------------------------------------------------
#image = recon(fid_binary, acqp, meth, reco, recoparts='default')
#print(image.shape)

output = '{}_{}'.format(data_loader._pvobj.subj_id,data_loader._pvobj.study_id)
mkdir(output)
if len(data.shape) == 7:
    print(data.shape)
    output_fname =f"{acqp._parameters['ACQ_scan_name'].strip().replace(' ','_')}"
    for c in range(data.shape[4]):
        ni_img  = nib.Nifti1Image(np.angle(np.squeeze(data[:,:,:,:,c,:,:])), affine=np.eye(4))
        nib.save(ni_img, os.path.join(output,f"{acqp._parameters['ACQ_scan_name'].strip().replace(' ','_')}_C{c}.nii.gz"))
    print('NifTi file is generated... [{}]'.format(output_fname))
        