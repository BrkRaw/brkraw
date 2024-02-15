"""
Created on Sat Feb 08 2024
 DEVELOPED FOR BRUKER PARAVISION 360 datasets
 Below code will work for 3D cartesian sequence 
 undersampled in the y-z phase view
 Reconstructions are completed with SIGPY

 THIS IS A WORK IN PROGRESS due to a lack of CS 
 datasets from PV360.3.3 or higher

@author: Tim Ho (UVA) 
"""

import sigpy as sp 
import sigpy.mri as mr
import numpy as np 

from .utils import get_value

def compressed_sensing_recon(data, acqp, meth, reco, lamda=0.01, method=None):
    # Meta Variables
    ky = get_value(meth,'PVM_EncGenSteps1')
    kz = get_value(meth,'PVM_EncGenSteps2')
    PVM_EncGenTotalSteps = get_value(meth, 'PVM_EncGenTotalSteps')

    kspaceShape = [1 for _ in range(7)] 
    RECO_ft_size = get_value(reco, 'RECO_ft_size')
    NI = get_value(acqp, 'NI')
    NR = get_value(acqp, 'NR')
    kspaceShape[1:len(RECO_ft_size)+1] = RECO_ft_size
    kspaceShape[0] = data.shape[1]
    kspaceShape[5] = NI 
    kspaceShape[6] = NR

    # Resort Raw Sorted to K-SPACE
    frame_sort = data.reshape((NR, PVM_EncGenTotalSteps, NI, kspaceShape[0], RECO_ft_size[0]))

    k_space = np.zeros(shape=kspaceShape, dtype=complex)
    for index, (i,j) in enumerate(zip(ky,kz)):
        k_space[:,:,int(i+max(ky)), j+max(kz)+1,0,:,:]= frame_sort[:,index,:,:,:].transpose(2,3,1,0)


    N1, N2, N3, N4, N5, N6, N7 = k_space.shape
    output = np.zeros(shape=(N2,N3,N4,N6,N7), dtype=complex)
    for NR in range(N7):
        for NI in range(N6):
            k_space = np.squeeze(k_space[:,:,:,:,:,NI,NR])
            # Compressed Sensing
            sens = mr.app.EspiritCalib(k_space).run()
            output[:,:,:,NI,NR] = mr.app.L1WaveletRecon(k_space, sens, lamda=lamda).run()
    
    return output