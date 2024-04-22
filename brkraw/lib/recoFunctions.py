# -*- coding: utf-8 -*-
"""
 DEVELOPED FOR BRUKER PARAVISION 360 datasets
 Functions below are made to support functions
 in recon.py
"""

import numpy as np
import warnings
    
def phase_rotate(frame, RECO_rotate, framenumber):
    
    if RECO_rotate.shape[1] > framenumber:
        RECO_rotate =  RECO_rotate[:, framenumber]
        RECO_rotate -= 0.5
    else:
        RECO_rotate =  RECO_rotate[:,0]
    
    # calculate additional variables
    dims = [frame.shape[0], frame.shape[1], frame.shape[2]]

    # Create Shift matrix in KSPACE
    phase_matrix = np.ones(shape=dims,dtype=complex)
    for index in range(len(RECO_rotate)):
        f = np.arange(dims[index])
        phase_vector = np.exp(1j*2*np.pi*(1-RECO_rotate[index])*f)
        if index == 0:
            phase_matrix *= np.tile(phase_vector[:,np.newaxis,np.newaxis], [1, dims[1], dims[2]])
        elif index == 1:
            phase_matrix *= np.tile(phase_vector[np.newaxis,:,np.newaxis], [dims[0], 1, dims[2]])
        elif index == 2:
            tmp = np.zeros((1,1,dims[2]), dtype=complex)
            tmp[0,0,:] = phase_vector
            phase_matrix *= np.tile(tmp, [dims[0], dims[1], 1])
    
    return phase_matrix

# Replace with zero padding
def zero_filling(frame, RECO_ft_size, signal_position=np.array([0.5,0.5,0.5])):
    # Check if Reco.RECO_ft_size is not equal to size(frame)
    not_Equal = any([(i != j) for i,j in zip(frame.shape,RECO_ft_size)])
    if not_Equal:
        if any(signal_position > 1) or any(signal_position < 0):
            warnings.warn('Signal needs to be between 0 and 1\nDefaulting to 0.5')
            signal_position=np.array([0.5,0.5,0.5])

        # calculate additional variables
        dims = (frame.shape[0], frame.shape[1], frame.shape[2])

        # start process
        newframe = np.zeros(RECO_ft_size, dtype=complex)
        startpos = np.zeros(len(RECO_ft_size), dtype=int)
        pos_ges = [None] * 3

        for i in range(len(RECO_ft_size)):
            diff = RECO_ft_size[i] - frame.shape[i] + 1
            startpos[i] = int(np.floor(diff * signal_position[i] + 1))
            if startpos[i] > RECO_ft_size[i]:
                startpos[i] = RECO_ft_size[i]
            pos_ges[i] = slice(startpos[i] - 1, startpos[i] - 1 + dims[i])
        
        newframe[pos_ges[0], pos_ges[1], pos_ges[2]] = frame
        del startpos, pos_ges

    else:
        newframe = frame
    return newframe


def phase_corr(frame):
    checkerboard = np.ones(shape=frame.shape[:3])
    # Use NumPy broadcasting to alternate the signs
    checkerboard[::2,::2,::2] = -1
    checkerboard[1::2,1::2,::2] = -1
    checkerboard[::2,1::2,1::2] = -1
    checkerboard[1::2,::2,1::2] = -1
    checkerboard *= -1
    return checkerboard