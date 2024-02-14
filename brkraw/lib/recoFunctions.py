# -*- coding: utf-8 -*-
"""
 DEVELOPED FOR BRUKER PARAVISION 360 datasets
 Functions below are made to support functions
 in recon.py

@author: Tim Ho (UVA) 
"""

from .utils import get_value
import numpy as np

def reco_qopts(frame, Reco, actual_framenumber):

    # import variables
    RECO_qopts = get_value(Reco, 'RECO_qopts') 

    # claculate additional parameters
    dims = [frame.shape[0], frame.shape[1], frame.shape[2], frame.shape[3]]

    # check if the qneg-Matrix is necessary:
    use_qneg = False
    if (RECO_qopts.count('QUAD_NEGATION') + RECO_qopts.count('CONJ_AND_QNEG')) >= 1:
        use_qneg = True
        qneg = np.ones(frame.shape)  # Matrix containing QUAD_NEGATION multiplication matrix

    # start process
    for i in range(len(RECO_qopts)):
        if RECO_qopts[i] == 'COMPLEX_CONJUGATE':
            frame = np.conj(frame)
        elif RECO_qopts[i] == 'QUAD_NEGATION':
            if i == 0:
                qneg = qneg * np.tile([[1, -1]], [np.ceil(dims[0]/2), dims[1], dims[2], dims[3]])
            elif i == 1:
                qneg = qneg * np.tile([[1], [-1]], [dims[0], np.ceil(dims[1]/2), dims[2], dims[3]])
            elif i == 2:
                tmp = np.zeros([1, 1, dims[2], 2])
                tmp[0, 0, :, :] = [[1, -1]]
                qneg = qneg * np.tile(tmp, [dims[0], dims[1], np.ceil(dims[2]/2), dims[3]])
            elif i == 3:
                tmp = np.zeros([1, 1, 1, dims[3], 2])
                tmp[0, 0, 0, :, :] = [[1, -1]]
                qneg = qneg * np.tile(tmp, [dims[0], dims[1], dims[2], np.ceil(dims[3]/2)])
        elif RECO_qopts[i] == 'CONJ_AND_QNEG':
            frame = np.conj(frame)
            if i == 0:
                qneg = qneg * np.tile([[1, -1]], [np.ceil(dims[0]/2), dims[1], dims[2], dims[3]])
            elif i == 1:
                qneg = qneg * np.tile([[1], [-1]], [dims[0], np.ceil(dims[1]/2), dims[2], dims[3]])
            elif i == 2:
                tmp = np.zeros([1, 1, dims[2], 2])
                tmp[0, 0, :, :] = [[1, -1]]
                qneg = qneg * np.tile(tmp, [dims[0], dims[1], np.ceil(dims[2]/2), dims[3]])
            elif i == 3:
                tmp = np.zeros([1, 1, 1, dims[3], 2])
                tmp[0, 0, 0, :, :] = [[1, -1]]
                qneg = qneg * np.tile(tmp, [dims[0], dims[1], dims[2], np.ceil(dims[3]/2)])
    
    if use_qneg:
        if qneg.shape != frame.shape:
            qneg = qneg[0:dims[0], 0:dims[1], 0:dims[2], 0:dims[3]]
        frame = frame * qneg
    
    return frame

    
def reco_phase_rotate(frame, Reco, actual_framenumber):
    
    # import variables
    RECO_rotate_all = get_value(Reco,'RECO_rotate')

    
    if RECO_rotate_all.shape[1] > actual_framenumber:
        RECO_rotate =  get_value(Reco,'RECO_rotate')[:, actual_framenumber]
    else:
        RECO_rotate =  get_value(Reco,'RECO_rotate')[:,0]
    
    if isinstance( get_value(Reco,'RECO_ft_mode'), list):
        if any(x != get_value(Reco,'RECO_ft_mode')[0] for x in get_value(Reco,'RECO_ft_mode')):
            raise ValueError('It''s not allowed to use different transfomations on different Dimensions: ' + Reco['RECO_ft_mode'])
        RECO_ft_mode = get_value(Reco,'RECO_ft_mode')[0]
    else:
        RECO_ft_mode = get_value(Reco,'RECO_ft_mode')

    # calculate additional variables
    dims = [frame.shape[0], frame.shape[1], frame.shape[2], frame.shape[3]]

    # start process
    phase_matrix = np.ones_like(frame)
    for index in range(len(RECO_rotate)):
        f = np.arange(dims[index])

        if RECO_ft_mode in ['COMPLEX_FT', 'COMPLEX_FFT']:
            phase_vector = np.exp(1j*2*np.pi*RECO_rotate[index]*f)
        elif RECO_ft_mode in ['NO_FT', 'NO_FFT']:
            phase_vector = np.ones_like(f)
        elif RECO_ft_mode in ['COMPLEX_IFT', 'COMPLEX_IFFT']:
            phase_vector = np.exp(1j*2*np.pi*(1-RECO_rotate[index])*f)
        else:
            raise ValueError('Your RECO_ft_mode is not supported')

        if index == 0:
            phase_matrix *= np.tile(phase_vector[:,np.newaxis,np.newaxis,np.newaxis], [1, dims[1], dims[2], dims[3]])
        elif index == 1:
            phase_matrix *= np.tile(phase_vector[np.newaxis,:,np.newaxis,np.newaxis], [dims[0], 1, dims[2], dims[3]])
        elif index == 2:
            tmp = np.zeros((1,1,dims[2],1), dtype=complex)
            tmp[0,0,:,0] = phase_vector
            phase_matrix *= np.tile(tmp, [dims[0], dims[1], 1, dims[3]])
        elif index == 3:
            tmp = np.zeros((1,1,1,dims[3]), dtype=complex)
            tmp[0,0,0,:] = phase_vector
            phase_matrix *= np.tile(tmp, [dims[0], dims[1], dims[2], 1])

    frame *= phase_matrix
    return frame


def reco_zero_filling(frame, Reco, actual_framenumber, signal_position):
    # check input
    RECO_ft_mode = get_value(Reco,'RECO_ft_mode')
    
    # Check if Reco.RECO_ft_size is not equal to size(frame)
    not_Equal = any([(i != j) for i,j in zip(frame.shape,get_value(Reco, 'RECO_ft_size'))])
        
    if not_Equal:
        if any(signal_position > 1) or any(signal_position < 0):
            raise ValueError('signal_position has to be a vector between 0 and 1')

        RECO_ft_size = get_value(Reco,'RECO_ft_size')

        # check if ft_size is correct:
        for i in range(len(RECO_ft_size)):
            if RECO_ft_size[i] < frame.shape[i]:
                raise ValueError('RECO_ft_size has to be bigger than the size of your data-matrix')

        # calculate additional variables
        dims = (frame.shape[0], frame.shape[1], frame.shape[2], frame.shape[3])

        # start process

        # Dimensions of frame and RECO_ft_size doesn't match? -> zero filling
        if not_Equal:
            newframe = np.zeros(RECO_ft_size, dtype=complex)
            startpos = np.zeros(len(RECO_ft_size), dtype=int)
            pos_ges = [None] * 4

            for i in range(len(RECO_ft_size)):
                diff = RECO_ft_size[i] - frame.shape[i] + 1
                startpos[i] = int(np.floor(diff * signal_position[i] + 1))
                if startpos[i] > RECO_ft_size[i]:
                    startpos[i] = RECO_ft_size[i]
                pos_ges[i] = slice(startpos[i] - 1, startpos[i] - 1 + dims[i])
                
            newframe[pos_ges[0], pos_ges[1], pos_ges[2], pos_ges[3]] = frame
        else:
            newframe = frame

        del startpos, pos_ges

    else:
        newframe = frame

    return newframe


def reco_FT(frame, Reco, actual_framenumber):
    """
    Perform Fourier Transform on the input frame according to the specified RECO_ft_mode in the Reco dictionary.
    
    Args:
    frame: ndarray
        Input frame to perform Fourier Transform on
    Reco: dict
        Dictionary containing the specified Fourier Transform mode (RECO_ft_mode)
    actual_framenumber: int
        Index of the current frame
    
    Returns:
    frame: ndarray
        Output frame after Fourier Transform has been applied
    """
    
    # Import variables
    RECO_ft_mode = get_value(Reco,'RECO_ft_mode')[0]
    
    # Start process
    if RECO_ft_mode in ['COMPLEX_FT', 'COMPLEX_FFT']:
        frame = np.fft.fftn(frame)
        #frame = sp.fft(frame, axes=[0,1,2], center=False)
    elif RECO_ft_mode in ['NO_FT', 'NO_FFT']:
        pass
    elif RECO_ft_mode in ['COMPLEX_IFT', 'COMPLEX_IFFT']:
        frame = np.fft.ifftn(frame)
        #frame = sp.ifft(frame, axes=[0,1,2], center=False)
    else:
        raise ValueError('Your RECO_ft_mode is not supported')
        
    return frame


def reco_phase_corr_pi(frame, Reco, actual_framenumber):
    # start process
    checkerboard = np.ones(shape=frame.shape)

    # Use NumPy broadcasting to alternate the signs
    checkerboard[::2,::2,::2,0] = -1
    checkerboard[1::2,1::2,::2,0] = -1
    
    checkerboard[::2,1::2,1::2,0] = -1
    checkerboard[1::2,::2,1::2,0] = -1
    
    frame = frame * checkerboard * -1
    
    return frame

  
def reco_cutoff(frame, Reco, actual_framenumber):
    """
    Crops the input frame according to the specified RECO_size in the Reco dictionary.
    
    Args:
    frame: ndarray
        Input frame to crop
    Reco: dict
        Dictionary containing the specified crop size (RECO_size) and offset (RECO_offset)
    actual_framenumber: int
        Index of the current frame
    
    Returns:
    newframe: ndarray
        Cropped output frame
    """
    
    # Use function only if Reco.RECO_size is not equal to size(frame)
    dim_equal = True
    for i,j in zip(get_value(Reco,'RECO_size'), frame.shape):
        dim_equal = (i==j)
   
    if not dim_equal:
        
        # Import variables
        RECO_offset = get_value(Reco,'RECO_offset')[:, actual_framenumber]
        RECO_size = get_value(Reco, 'RECO_size')
        
        # Cut the new part with RECO_size and RECO_offset
        pos_ges = []
        for i in range(len(RECO_size)):

            pos_ges.append(slice(RECO_offset[i], RECO_offset[i] + RECO_size[i]))
        newframe = frame[tuple(pos_ges)]
    else:
        newframe = frame
    
    return newframe


def reco_scale_phase_channels(frame, Reco, channel):
    # check input
    reco_scale = get_value(Reco,'RecoScaleChan')
    if not isinstance(reco_scale, list):
        reco_scale = [reco_scale]
    if channel <= len(reco_scale) and reco_scale != None:
        scale = reco_scale[int(channel)]
    else:
        scale = 1.0
    
    reco_phase = get_value(Reco,'RecoPhaseChan')

    if not isinstance(reco_phase, list):
        reco_phase = [reco_phase]
    if channel <= len(reco_phase) and reco_phase != None:
        phase = reco_phase[int(channel)]
    else:
        phase = 0.0
        
    spFactor = scale * np.exp(1j * phase * np.pi / 180.0)
    # multiply each pixel by common scale and phase factor
    frame = spFactor * frame
    return frame


def reco_sumofsquares(frame, Reco): 
    out = np.sqrt( np.sum(np.square(np.abs(frame)), axis=4, keepdims=True) )
    return out


def reco_transposition(frame, Reco, actual_framenumber):
    # Import variables
    RECO_transposition = get_value(Reco,'RECO_transposition')[actual_framenumber - 1]
    
    # Calculate additional variables
    dims = [frame.shape[i] for i in range(4)]
    
    # Start process
    if RECO_transposition > 0:
        ch_dim1 = (RECO_transposition % 4)
        ch_dim2 = RECO_transposition - 1
        new_order = list(range(4))
        new_order[int(ch_dim1)] = ch_dim2
        new_order[int(ch_dim2)] = ch_dim1
        frame = np.transpose(frame, new_order)
        frame = np.reshape(frame, dims)
    
    return frame