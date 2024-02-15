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

import brkbart
from bart import bart

import sigpy as sp
from sigpy import mri as mr
from sigpy import plot as pl

import nibabel as nib

PV_zipfile = "/home/jac/data/nmrsu_data/Tim_Wilson_Tim_207023_1_Default_20231202FeCl3_210800_360.3.4.PvDatasets"
data_loader = br.load(PV_zipfile)

print(data_loader._avail.keys())
ExpNum = 10

# Raw data processing for single job
fid_binary = data_loader.get_fid(ExpNum)
acqp = data_loader.get_acqp(ExpNum)
meth = data_loader.get_method(ExpNum)
reco = data_loader._pvobj.get_reco(ExpNum, 1)

print(get_value(acqp, 'ACQ_protocol_name' ), ExpNum)
print('DIMS:', get_value(acqp, 'ACQ_dim' ))
# process OPTIONS: 'raw', 'frame', 'CKdata', 'image'    
process = 'CKdata' 

# KSPACE DATA
data = recon(fid_binary, acqp, meth, reco, process=process, recoparts='all')

# REFERENCE DATA
image = recon(fid_binary, acqp, meth, reco, process='image', 
              recoparts=['quadrature', 'phase_rotate', 'zero_filling', 'FT', 'phase_corr_pi', 
                        'cutoff',  'scale_phase_channels', 'sumOfSquares', 'transposition']
                        )
image = np.squeeze(image)[:,:,:,0]
data = data/np.max(np.abs(data)) # Normalize Data
print(data.shape)

# SIMULATE POISSON UNDERSAMPLING 
# NOTE coil dim is moved to first index for SIGPY standards 
undersampled_data = np.zeros_like(data).transpose(4,0,1,2,3,5,6)
poisson = mr.poisson(data.shape[1:3],2)
for i in range(data.shape[4]):
    for j in range(data.shape[5]):
        for k in range(data.shape[6]):
            undersampled_data[i,:,:,:,0,j,k] = data[:,:,:,0,i,j,k]*np.stack([poisson for _ in range(128)])

# Use only one set of data [coil,x,y,z,_,TE,TR]
undersampled_data = undersampled_data[:,:,:,:,0,0,0]
reconzf = sp.ifft(undersampled_data, axes=[1,2,3])


# COMPRESSED SENSING -------------------
sens = mr.app.EspiritCalib(undersampled_data).run()
#pl.ImagePlot(sens, z=0, title='Sensitivity Maps Estimated by ESPIRiT')
"""
lamda = 1
img_sense = mr.app.SenseRecon(undersampled_data, sens, lamda=lamda).run()
"""
lamda = 0.0002
img_L1 = mr.app.L1WaveletRecon(undersampled_data, sens, lamda=lamda).run()

lamda = 0.001
img_tv = mr.app.TotalVariationRecon(undersampled_data, sens, lamda=lamda).run()


#pl.ImagePlot(image, title='Fully Sampled')
#pl.ImagePlot(reconzf, title='Zero-fill Reconstruction')
#pl.ImagePlot(img_sense, title='SENSE Reconstruction')
#pl.ImagePlot(img_L1, title='L1Wavelet Reconstruction')
#pl.ImagePlot(img_tv, title='Total Variation Regularized Reconstruction')