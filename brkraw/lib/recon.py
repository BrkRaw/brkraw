# -*- coding: utf-8 -*-
"""
Created on Sat Jan  20 10:06:38 2024
 DEVELOPED FOR BRUKER PARAVISION 360 datasets
 Below code will work for cartesian sequence
 GRE, MSME, RARE that were acquired with linear
 phase encoding

@author: Tim Ho (UVA) 
"""

from .utils import get_value, set_value
from .recoFunctions import *
from .recoSigpy import compressed_sensing_recon
import numpy as np
from copy import deepcopy


def recon(fid_binary, acqp, meth, reco, process = None, recoparts = 'default'):
    """ Process FID -> Channel Sorted -> Frame-Sorted -> K-Sorted -> Image
    
    Parameters
    ----------
    fid_binary : bytestring

    acqp : dict (brkraw Parameter structure)

    meth : dict (brkraw Parameter structure)

    reco : dict (brkraw Parameter structure)

    process: 'raw', 'frame', 'CKdata', 'image'

    recoparts: 'default' or list()
        List Options: ['quadrature', 'phase_rotate', 'zero_filling', 'FT', 'phase_corr_pi', 
                        'cutoff',  'scale_phase_channels', 'sumOfSquares', 'transposition']
        
        'default':
            recoparts = ['quadrature', 'phase_rotate', 'zero_filling', 
                        'FT', 'phase_corr_pi']

    Returns
    -------
    output : np.array 

    """
    output = readBrukerRaw(fid_binary, acqp, meth)
    if process == 'raw':
        return output
    
    # IF CORRECT SEQUENCES
    if  'rare'      in get_value(acqp, 'ACQ_protocol_name').lower() or \
        'msme'      in get_value(acqp, 'ACQ_protocol_name').lower() or \
        'localizer' in get_value(acqp, 'ACQ_protocol_name').lower() or \
        'gre'       in get_value(acqp, 'ACQ_protocol_name').lower() or \
        'mge'       in get_value(acqp, 'ACQ_protocol_name').lower() or \
        'FLASH.ppg' == get_value(acqp, 'PULPROG'):

        # Compressed Sensing
        if get_value(meth,'PVM_EncCS') == 'Yes':
            print(get_value(acqp, 'ACQ_scan_name' ))
            print("Warning: Compressed Sensing is IN TESTING...")
            output = compressed_sensing_recon(output, acqp, meth, reco)
            return output

        # Full Cartesian Pipeline
        output = convertRawToFrame(output, acqp, meth)
        if process == 'frame':
            return output
        
        output = convertFrameToCKData(output, acqp, meth)
        if process == 'CKdata':
            return output
        
        output = brkraw_Reco(output, deepcopy(reco), meth, recoparts = recoparts)
    
    else:
        print("Warning: SEQUENCE PROTOCOL {} NOT SUPPORTED...".format(get_value(acqp, 'ACQ_scan_name' )))
        print("returning 'raw' sorting")

    return output


def readBrukerRaw(fid_binary, acqp, meth):
    """ Sorts FID into a 3D np matrix [num_readouts, channel, scan_size]

    Parameters
    ----------
    fid_binary : bytestring

    acqp : dict (brkraw Parameter structure)

    meth : dict (brkraw Parameter structure)
        

    Returns
    -------
    X : np.array [num_lines, channel, scan_size]
    """
    from .reference import BYTEORDER, WORDTYPE
    # META DATA
    NI = get_value(acqp, 'NI')
    NR = get_value(acqp, 'NR')

    dt_code = 'int32' 
    if get_value(acqp, 'ACQ_ScanPipeJobSettings') != None:
        if get_value(acqp, 'ACQ_ScanPipeJobSettings')[0][1] == 'STORE_64bit_float':
            dt_code = 'float64' 
    
    if '32' in dt_code:
        bits = 32 # Need to add a condition here
    elif '64' in dt_code:
        bits = 64
    DT_CODE = np.dtype(dt_code)

    BYTORDA = get_value(acqp, 'BYTORDA') 
    if BYTORDA == 'little':
        DT_CODE = DT_CODE.newbyteorder('<')
    elif BYTORDA == 'big':
        DT_CODE = DT_CODE.newbyteorder('>')

    # Get FID FROM buffer
    fid = np.frombuffer(fid_binary, DT_CODE)
    
    # Sort raw data
    if '360' in get_value(acqp,'ACQ_sw_version'):
        # META data
        ACQ_size = get_value(acqp, 'ACQ_jobs')[0][0]
        numDataHighDim = np.prod(ACQ_size)
        nRecs = get_value(acqp, 'ACQ_ReceiverSelectPerChan').count('Yes')
        
        jobScanSize = get_value(acqp, 'ACQ_jobs')[0][0]
        
        # Assume data is complex
        X = fid[::2] + 1j*fid[1::2] 
        
        # [num_lines, channel, scan_size]
        X = np.reshape(X, [-1, nRecs, int(jobScanSize/2)])

    else:
                
        nRecs = 1 # PV7 only save 1 channel
        if get_value(acqp, 'ACQ_ReceiverSelect') != None:
            nRecs = get_value(acqp, 'ACQ_ReceiverSelect').count('Yes')
            
        
        ACQ_size = get_value(acqp, 'ACQ_size' )
        if type(ACQ_size) == int:
            ACQ_size = [ACQ_size] 

        if get_value(acqp, 'GO_block_size') == 'Standard_KBlock_Format':
            blocksize = int(np.ceil(ACQ_size[0]*nRecs*(bits/8)/1024)*1024/(bits/8))
        else:
            blocksize = int(ACQ_size[0]*nRecs)

        # CHECK SIZE
        if fid.size != blocksize*np.prod(ACQ_size[1:])*NI*NR:
            raise Exception('readBrukerRaw 150: Error Size dont match')
            #print('readBrukerRaw 150: Error Size dont match')

        # Reshape
        fid = fid[::2] + 1j*fid[1::2] 
        fid = fid.reshape([-1,blocksize//2])
        #print(nRecs)
        # THIS REMOVES ZERO FILL (IDK THE PURPOSE FOR THIS)
        if blocksize != ACQ_size[0]*nRecs:
            fid = fid[:,:ACQ_size[0]//2*nRecs]
            fid = fid.reshape((-1,nRecs,ACQ_size[0]//2))
            X = fid.transpose(0,1,2)
            
        else:
            # UNTESTED TIM FEB 12 2024 (IDK WHAT THIS DOES)
            X = fid.reshape((ACQ_size[0]//2, nRecs, -1))
        
    return X


def convertRawToFrame(data, acqp, meth):
    """ Prelinary raw fid sorting

    Parameters
    ----------
    data : np.array with size [num_readouts, channel, scan_size]

    acqp : dict (brkraw Parameter structure)

    meth : dict (brkraw Parameter structure)

    Returns
    -------
    frame : np.array with size 
        [scansize, ACQ_phase_factor, numDataHighDim/ACQ_phase_factor, numSelectedReceivers, NI, NR]
    """ 
 
    results = data.copy()
     
    # Turn Raw into frame
    NI = get_value(acqp, 'NI')
    NR = get_value(acqp, 'NR')
    
    if 'rare' in get_value(meth,'Method').lower():
        ACQ_phase_factor    = get_value(meth,'PVM_RareFactor')    
    else:
        ACQ_phase_factor    = get_value(acqp,'ACQ_phase_factor')
    
    ACQ_obj_order       = get_value(acqp, 'ACQ_obj_order')
    if isinstance(ACQ_obj_order, int):
        ACQ_obj_order = [ACQ_obj_order]
    
    ACQ_dim             = get_value(acqp, 'ACQ_dim')
    numSelectedRecievers= results.shape[-2]
    
    acqSizes = np.zeros(ACQ_dim)
    scanSize = get_value(acqp, 'ACQ_jobs')[0][0]
    # FIXES for PV 7
    if scanSize == 0:
        scanSize = get_value(acqp,'ACQ_size')[0]
    
    isSpatialDim = [i == 'Spatial' for i in get_value(acqp, 'ACQ_dim_desc')]
    spatialDims = sum(isSpatialDim)
    
    if isSpatialDim[0]:
        if spatialDims == 3:
            acqSizes[1:] = get_value(meth, 'PVM_EncMatrix')[1:]
        elif spatialDims == 2:
            acqSizes[1]  = get_value(meth, 'PVM_EncMatrix')[1]
    
    numresultsHighDim=np.prod(acqSizes[1:])
    acqSizes[0] = scanSize   

    if np.iscomplexobj(results):
        scanSize = int(acqSizes[0]/2)
    else:  
        scanSize = acqSizes[0]
    
    # Resort
    if ACQ_dim>1:
        # [num_readout, channel, scan_size] -> [channel, scan_size, num_readout]
        results = results.transpose((1,2,0))
        
        results = results.reshape(
            int(numSelectedRecievers), 
            int(scanSize), 
            int(ACQ_phase_factor), 
            int(NI), 
            int(numresultsHighDim/ACQ_phase_factor), 
            int(NR), order='F')
        
        # reorder to [scansize, ACQ_phase_factor, numDataHighDim/ACQ_phase_factor, numSelectedReceivers, NI, NR]
        results = np.transpose(results, (1, 2, 4, 0, 3, 5)) 
    
        results =  results.reshape( 
            int(scanSize), 
            int(numresultsHighDim), 
            int(numSelectedRecievers), 
            int(NI), 
            int(NR), order='F') 
        
        frame = np.zeros_like(results)
        frame[:,:,:,ACQ_obj_order,:] = results 
        
    else:
        # Havent encountered this situation yet
        # Leaving code in just in case
        '''
        results = np.reshape(results,(numSelectedRecievers, scanSize,1,NI,NR), order='F')
        return_out = np.zeros_like(results)
        return_out = np.transpose(results, (1, 2, 0, 3, 4))
        frame = return_out'''
        raise 'Bug here 120'
        
    
    return frame


def convertFrameToCKData(frame, acqp, meth):
    """Frame to unprocessed KSPACE

    Parameters
    ----------
    frame : np.array with size [num_readouts, channel, scan_size]

    acqp : dict (brkraw Parameter structure)

    meth : dict (brkraw Parameter structure)

    Returns
    -------
    data : np.array with size 
        [scansize, ACQ_phase_factor, numDataHighDim/ACQ_phase_factor, numSelectedReceivers, NI, NR]
        for simplified understanding of the data structure
        [x,y,z,_,n_channel,NI,NR]
    """
    NI = get_value(acqp, 'NI')
    NR = get_value(acqp, 'NR')
    
    ACQ_phase_factor    = get_value(acqp,'ACQ_phase_factor')
    ACQ_obj_order       = get_value(acqp, 'ACQ_obj_order')
    ACQ_dim             = get_value(acqp, 'ACQ_dim')
    numSelectedReceivers= frame.shape[2]
    
    acqSizes = np.zeros(ACQ_dim)
    
    scanSize = get_value(acqp, 'ACQ_jobs')[0][0]
    # FIXES for PV 7
    if scanSize == 0:
        scanSize = get_value(acqp,'ACQ_size')[0]
        
    acqSizes[0] = scanSize
    ACQ_size = acqSizes
    
    isSpatialDim = [i == 'Spatial' for i in get_value(acqp, 'ACQ_dim_desc')]
    spatialDims = sum(isSpatialDim)
    
    if isSpatialDim[0]:
        if spatialDims == 3:
            acqSizes[1:] = get_value(meth, 'PVM_EncMatrix')[1:]
        elif spatialDims == 2:
            acqSizes[1]  = get_value(meth, 'PVM_EncMatrix')[1]
    numDataHighDim=np.prod(acqSizes[1:])
    
    if np.iscomplexobj(frame):
        scanSize = int(acqSizes[0]/2)
    else:
        scanSize = acqSizes[0]
    
    if ACQ_dim==3:
       
        PVM_EncSteps2=get_value(meth, 'PVM_EncSteps2')
        assert PVM_EncSteps2 != None
           
    PVM_Matrix = get_value(meth, 'PVM_Matrix')
    PVM_EncSteps1 = get_value(meth,'PVM_EncSteps1')
    
    PVM_AntiAlias = get_value(meth, 'PVM_AntiAlias')
    if PVM_AntiAlias == None:
        # No anti-aliasing available.
        PVM_AntiAlias = np.ones((ACQ_dim))
     
    PVM_EncZf=get_value(meth, 'PVM_EncZf')
    
    if PVM_EncZf == None:
        # No zero-filling/interpolation available.
        PVM_EncZf = np.ones((ACQ_dim))
    
    # Resort
    
    frameData = frame.copy()
    
    # MGE with alternating k-space readout: Reverse every second scan. 
    if get_value(meth, 'EchoAcqMode') != None and get_value(meth,'EchoAcqMode') == 'allEchoes':
        frameData[:,:,:,1::2,:] = np.flipud(frame[:,:,:,1::2,:])
    
    
    # Calculate size of Cartesian k-space
    # Step 1: Anti-Aliasing
    ckSize = np.round(np.array(PVM_AntiAlias)*np.array(PVM_Matrix))
    # Step 2: Interpolation 

    reduceZf = 2*np.floor( (ckSize - ckSize/np.array(PVM_EncZf))/2 )
    ckSize = ckSize - reduceZf
    
    # # index of central k-space point (+1 for 1-based indexing in MATLAB) 
    ckCenterIndex = np.floor(ckSize/2 + 0.25) + 1

    readStartIndex = int(ckSize[0]-scanSize + 1)
    

    # Reshape & store
    # switch ACQ_dim
    if ACQ_dim == 1:
        frameData = np.reshape(frameData,(scanSize, 1, 1, 1, numSelectedReceivers, NI, NR) , order='F')
        data = np.zeros((ckSize[0], 1, 1, 1, numSelectedReceivers, NI, NR), dtype=complex)
        data[readStartIndex-1:,0,0,0,:,:,:] = frameData

    elif ACQ_dim == 2: 
        frameData=np.reshape(frameData,(scanSize, int(ACQ_size[1]), 1, 1, numSelectedReceivers, NI, NR) , order='F')
        data=np.zeros([int(ckSize[0]), int(ckSize[1]), 1, 1, numSelectedReceivers, NI, NR], dtype=complex)
        encSteps1indices = (PVM_EncSteps1 + ckCenterIndex[1] - 1).astype(int)
        data[readStartIndex-1:,encSteps1indices,0,0,:,:,:] = frameData.reshape(data[readStartIndex-1:,encSteps1indices,0,0,:,:,:].shape, order='F')               
    
    elif ACQ_dim == 3:
        frameData = np.reshape(frameData,(scanSize, int(ACQ_size[1]), int(ACQ_size[2]), 1, numSelectedReceivers, NI, NR) , order='F')
        data=np.zeros([int(ckSize[0]), int(ckSize[1]), int(ckSize[2]), 1, numSelectedReceivers, NI, NR], dtype=complex)
        encSteps1indices = (PVM_EncSteps1 + ckCenterIndex[1] - 1).astype(int)
        encSteps2indices = (PVM_EncSteps2 + ckCenterIndex[2] - 1).astype(int)
        
        data[readStartIndex-1:,list(encSteps1indices),:,:,:,:,:] = frameData[:,:,list(encSteps2indices),:,:,:,:]
    
    else:
        raise 'Unknown ACQ_dim with useMethod'
    
    return data


def brkraw_Reco(kdata, reco, meth, recoparts = 'all'):
    reco_result = kdata.copy()
        
    if recoparts == 'all':
        recoparts = ['quadrature', 'phase_rotate', 'zero_filling', 'FT', 'phase_corr_pi', 
                     'cutoff',  'scale_phase_channels', 'sumOfSquares', 'transposition']
    elif recoparts == 'default':
        recoparts = ['quadrature', 'phase_rotate', 'zero_filling', 
                     'FT', 'phase_corr_pi']
    # Other stuff
    RECO_ft_mode = get_value(reco, 'RECO_ft_mode')  
 
    #if '360' in meth.headers['title'.upper()]:
    reco_ft_mode_new = []
    
    for i in RECO_ft_mode:
        if i == 'COMPLEX_FT' or i == 'COMPLEX_FFT':
            reco_ft_mode_new.append('COMPLEX_IFT')
        else:
            reco_ft_mode_new.append('COMPLEX_FT')
            
    reco = set_value(reco, 'RECO_ft_mode', reco_ft_mode_new)
    RECO_ft_mode = get_value(reco, 'RECO_ft_mode')
    
    # Adapt FT convention to acquisition version.
    N1, N2, N3, N4, N5, N6, N7 = kdata.shape

    dims = kdata.shape[0:4]
    for i in range(4):
        if dims[i]>1:
            dimnumber = (i+1)
        
    NINR=kdata.shape[5]*kdata.shape[6]
    signal_position=np.ones(shape=(dimnumber,1))*0.5
    
    same_transposition = True
    RECO_transposition = get_value(reco, 'RECO_transposition')

    if not isinstance(RECO_transposition, list):
        RECO_transposition = [RECO_transposition]
    for i in RECO_transposition:
        if i != RECO_transposition[0]:
            same_transposition = False
    
    map_index= np.reshape( np.arange(0,kdata.shape[5]*kdata.shape[6]), (kdata.shape[6], kdata.shape[5]) ).flatten()
    
    # --- START RECONSTRUCTION ---
    for recopart in recoparts:
        if 'quadrature' in recopart:
            for NR in range(N7):
                for NI in range(N6):
                    for channel in range(N5):
                        reco_result[:,:,:,:,channel,NI,NR] = reco_qopts(kdata[:,:,:,:,channel,NI,NR], reco, map_index[(NI+1)*(NR+1)-1])
                         
         
        if 'phase_rotate' in recopart:
            for NR in range(N7):
                for NI in range(N6):
                    for channel in range(N5):
                        reco_result[:,:,:,:,channel,NI,NR] = reco_phase_rotate(kdata[:,:,:,:,channel,NI,NR], reco, map_index[(NI+1)*(NR+1)-1])
          

        if 'zero_filling' in recopart:
            RECO_ft_size = get_value(reco,'RECO_ft_size')
            
            newdata_dims=[1, 1, 1, 1]

            newdata_dims[0:len(RECO_ft_size)] = RECO_ft_size
            newdata = np.zeros(shape=newdata_dims+[N5, N6, N7], dtype=np.complex128)

            for NR in range(N7):
                for NI in range(N6):
                    for chan in range(N5):
                        newdata[:,:,:,:,chan,NI,NR] = reco_zero_filling(reco_result[:,:,:,:,chan,NI,NR], reco, map_index[(NI+1)*(NR+1)-1], signal_position).reshape(newdata[:,:,:,:,chan,NI,NR].shape)
        
            reco_result=newdata    

        
        if 'FT' in recopart:
            RECO_ft_mode = get_value(reco,'RECO_ft_mode')[0]
            for NR in range(N7):
                for NI in range(N6):
                    for chan in range(N5):
                        reco_result[:,:,:,:,chan,NI,NR] = reco_FT(reco_result[:,:,:,:,chan,NI,NR], reco, map_index[(NI+1)*(NR+1)-1])


        if 'phase_corr_pi' in recopart:
            for NR in range(N7):
                for NI in range(N6):
                    for chan in range(N5):
                        reco_result[:,:,:,:,chan,NI,NR] = reco_phase_corr_pi(reco_result[:,:,:,:,chan,NI,NR], reco, map_index[(NI+1)*(NR+1)-1])
        
        ''' # There is a current bug with cutoff function
        if 'cutoff' in recopart: 
            newdata_dims=[1, 1, 1, 1]
            reco_size = get_value(reco, 'RECO_size')
            newdata_dims[0:len(reco_size)] = reco_size
            newdata = np.zeros(shape=newdata_dims+[N5, N6, N7], dtype=np.complex128)
            
            for NR in range(N7):
                for NI in range(N6):
                    for chan in range(N5):
                        newdata[:,:,:,:,chan,NI,NR] = reco_cutoff(reco_result[:,:,:,:,chan,NI,NR], reco, map_index[(NI+1)*(NR+1)-1])
        
            reco_result=newdata
        '''

        if 'scale_phase_channels' in recopart: 
            for NR in range(N7):
                for NI in range(N6):
                    for chan in range(N5):
                        reco_result[:,:,:,:,chan,NI,NR] = reco_scale_phase_channels(reco_result[:,:,:,:,chan,NI,NR], reco, chan)
        
        
        if 'sumOfSquares' in recopart:
            reco_result = np.sqrt( np.sum(np.square(np.abs(reco_result)), axis=4, keepdims=True))
            reco_result = reco_result[:,:,:,:,:1,:,:]
            reco_result = np.real(reco_result)
            
            N5 = 1 # Update N5
    
        if 'transposition' in recopart:
            if same_transposition:
                # import variables
                RECO_transposition = RECO_transposition[0]
                # calculate additional variables:
            
                # start process
                if RECO_transposition > 0:
                    ch_dim1 = (RECO_transposition % len(kdata.shape)) 
                    ch_dim2 = RECO_transposition - 1 
                    new_order = [0, 1, 2, 3]
                    new_order[int(ch_dim1)] = int(ch_dim2)
                    new_order[int(ch_dim2)] = int(ch_dim1)
                    reco_result = reco_result.transpose(new_order + [4, 5, 6])
            else:
                for NR in range(N7):
                    for NI in range(N6):
                        for chan in range(N5):
                            reco_result[:,:,:,:,chan,NI,NR] = reco_transposition(reco_result[:,:,:,:,chan,NI,NR], reco, map_index[(NI+1)*(NR+1)-1])
    # --- End of RECONSTRUCTION Loop --- 


    return reco_result