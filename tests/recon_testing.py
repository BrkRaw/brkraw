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
from brkraw.lib.utils import get_value
import brkraw as br
from brkraw.lib.recon import recon


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

    # process OPTIONS: 'raw', 'frame', 'CKdata', 'image'    
    process = 'image' 
    
    # test functions
    
    start_time = time.time()
    data = recon(fid_binary, acqp, meth, reco, process=process)
    print("{} convert {} seconds".format (process, time.time()-start_time))
    data = data/np.max(np.abs(data)) # Normalize Data
    #print(data.shape)

        