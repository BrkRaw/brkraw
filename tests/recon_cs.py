import os
import time

import numpy as np
import matplotlib.pyplot as plt 

import brkraw as br
from brkraw.lib.recon import *

import sigpy as sp
from sigpy import mri as mr
from sigpy import plot as pl

import nibabel as nib


# TEST WITH FUNCTION 
folder = '/home/jac/data/data20230614'
MainDir = os.path.join(folder,'Price_Matt_7585_1_Default_CS_Trial_2_12718_360.3.4.PvDatasets')
print(MainDir)
i =8
rawdata = br.load(os.path.join(MainDir))
acqp        = rawdata.get_acqp(i)
meth        = rawdata.get_method(i)
reco        = rawdata._pvobj.get_reco(i,1)
fid_binary  = rawdata.get_fid(i)
data = recon(fid_binary, acqp, meth, reco, process='image')
print(data.shape)
pl.ImagePlot(np.squeeze(data))

data = recon(fid_binary, acqp, meth, reco, process='raw')
frame_test = convertRawToFrame(data, acqp, meth)
