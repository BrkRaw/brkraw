# -*- coding: utf-8 -*-
"""
Created on Sat Jan  20 10:06:38 2024
 DEVELOPED FOR BRUKER PARAVISION 6, 7, and 360 datasets
 Below are methods implemented for FID sorting into KSPACE
 and simple image reconstruction.
 MOST sequences are assumed to be cartesian
 
 This package was primarily created as an 
 intermediate for other image reconstruction 
 software such as MIRT and BART

# NOTES
# EPI is not fully working yet 
# T1_IG_FLASH_flc has an issue with size
# NEED to test compress sense for RARE
"""

from .recoFunctions import phase_rotate, phase_corr, zero_filling
from ..api.data import Scan
import numpy as np
import warnings

SUPPORTED_PROTOCOLS = ['rare','localizer' ,'gre', 'msme',      
                       'mge','dess', 'fisp', 'flash']

def reconstruction(scanobj,process='image', **kwargs):
    # Ensure Scans are Image Based
    acqp = scanobj.pvobj.acqp
    ACQ_dim_desc = [acqp.get('ACQ_dim_desc')] if isinstance(acqp.get('ACQ_dim_desc'), str) else acqp.get('ACQ_dim_desc')
    if 'Spectroscopic' in ACQ_dim_desc:
        warnings.warn('Scan is spectroscopic')
        process = 'readout' 
    
    # Reconstruction Processing
    recoObj = Reconstruction(scanobj)
    if process == 'readout':
        return recoObj.sort_fid()
    elif process == 'kspace':
        return recoObj.process_kspace()
    return recoObj.reconstruct(rms=kwargs['rms'] if 'rms' in kwargs.keys() else True) 

class Reconstruction:
    def __init__(self, scanobj:'Scan', reco_id:'int'=1) -> None:
        pvscan = scanobj.pvobj
        self.acqp       = pvscan.acqp
        self.method     = pvscan.method
        self.fid        = pvscan.get_fid()
        self.CS         = True if self.method.get('PVM_EncCS')=='Yes' else False
        self.NI         = self.acqp['NI']
        self.NR         = self.acqp['NR']
        self.NRecs      = 1
        self.reco_id    = reco_id
        self.info       = scanobj.get_info(self.reco_id)
        self.protocol   = self.info.protocol
        self.reco       = pvscan.get_reco(self.reco_id).reco        
        self.supported_protocol = any([True for i in SUPPORTED_PROTOCOLS if i in self.protocol['protocol_name'].lower()])
    
    # 1) Convert Buffer to a np array
    def sort_fid(self):
        """ Sorts FID into a 3D np matrix [num_readouts, channel, scan_size]

        Returns
        -------
        X : np.array [num_lines, channel, scan_size]
        """
        # META DATA
        dt_code = 'int32'
        if self.acqp.get('ACQ_ScanPipeJobSettings') != None: 
            if self.acqp['ACQ_ScanPipeJobSettings'][0][1] == 'STORE_64bit_float':
                dt_code = 'float64' 
    
        bits = 64 if '64' in dt_code else 32
        DT_CODE = np.dtype(dt_code)

        BYTORDA = self.acqp['BYTORDA'] 
        if BYTORDA == 'little':
            DT_CODE = DT_CODE.newbyteorder('<')
        elif BYTORDA == 'big':
            DT_CODE = DT_CODE.newbyteorder('>')

        # Get FID FROM buffer
        fid = np.frombuffer(self.fid.read(), DT_CODE)
        # Check Version and Sort fid data
        if '360' in self.protocol['sw_version']:
            # METAdata for 360
            self.NRecs = self.acqp['ACQ_ReceiverSelectPerChan'].count('Yes')
            scanSize = self.acqp['ACQ_jobs'][0][0]
            X = fid[::2] + 1j*fid[1::2]

        else:
            # METAdata Versions Before 360        
            self.NRecs = self.acqp.get('ACQ_ReceiverSelect').count('Yes') if self.acqp.get('ACQ_ReceiverSelect') != None else 1
            ACQ_size = self.acqp['ACQ_size'] if isinstance(self.acqp['ACQ_size'],int) else self.acqp['ACQ_size']
            scanSize = ACQ_size[0]
            if self.acqp['GO_block_size'] == 'Standard_KBlock_Format':
                blocksize = int(np.ceil(ACQ_size[0]*self.NRecs*(bits/8)/1024)*1024/(bits/8))
            else:
                blocksize = int(ACQ_size[0]*self.NRecs)

            # CHECK SIZE
            if fid.size != blocksize*np.prod(ACQ_size[1:])*self.NI*self.NR:
                raise ValueError('Error FID size dont match')

            # Convert to Complex
            X = fid[::2] + 1j*fid[1::2] 
            X = X.reshape([-1,blocksize//2])
    
            # Reshape Matrix [num_lines, channel, scan_size]
            if blocksize != scanSize*self.NRecs:
                X = X[:,:scanSize//2*self.NRecs]
        
        # [num_lines, channel, scan_size]
        X = X.reshape((-1, self.NRecs, scanSize//2))  
        
        return X
    
    # 2) Convert to KSPACE
    def sort_kspace(self, fid = None):
        """
        FID    = [num_lines, channel, scan_size]
        KSPACE = [kx,ky,kz,NRec,NI,NR]
        """
        if fid == None:
            fid = self.sort_fid()
        if not self.supported_protocol:   
            warnings.warn("SEQUENCE PROTOCOL {} NOT SUPPORTED YET...\nreturning readout sorted".format(self.acqp.get('ACQ_scan_name' )))
            return fid
        
        N_total, _, Nreadout = fid.shape
    
        # Meta data
        dims = self.acqp.get('ACQ_dim')
        obj_order = [self.acqp.get('ACQ_obj_order')] if isinstance(self.acqp.get('ACQ_obj_order'), int) else self.acqp.get( 'ACQ_obj_order')
        phase_factor = self.method.get('PVM_RareFactor') if 'rare' in self.method.get('Method').lower() else self.acqp.get('ACQ_phase_factor')

        PVM_Matrix = self.method.get('PVM_Matrix')
        kSize = np.round(np.array(self.method.get('PVM_AntiAlias'))*np.array(PVM_Matrix))
        zerofill = 2*np.floor( (kSize - kSize/np.array(self.method.get('PVM_EncZf')))/2 )
        kSize = kSize - zerofill
        center = np.floor(kSize/2)
        
        EncMatrix = self.method.get('PVM_EncMatrix')
        NPE = self.method.get('PVM_EncGenTotalSteps') if self.CS else np.prod(EncMatrix[1:])
        phase_encode2 = [0]
        if dims == 3:
            phase_encode2 = self.method.get('PVM_EncSteps2')
            phase_encode2 = (phase_encode2 + center[2]).astype(int)
        phase_encode1 = self.method.get('PVM_EncSteps1')
        phase_encode1 = (phase_encode1 + center[1]).astype(int)

        if self.method.get('PVM_IsEpiScan') == 'Yes':
            fid = fid.reshape(N_total,self.NRecs,int(Nreadout/kSize[0]),int(kSize[0])).transpose(2,0,1,3)
            fid = fid.reshape(-1,self.NRecs,int(kSize[0]))
            fid[1::2,:,:] = fid[1::2,:,::-1]
            Nreadout = int(kSize[0])
        readStart = int(kSize[0]-Nreadout)

        assert np.prod(fid.shape) == (Nreadout*NPE*self.NI*self.NRecs*self.NR), 'Method calculated size does not match size of fid'
        
        temp = np.zeros([int(kSize[0]), int(kSize[1]),int(kSize[2]) if dims == 3 else 1, self.NRecs, self.NI, self.NR], dtype=complex)
        if self.CS:
            warnings.warn('Compressed Sensing has only been tested on undersampled GRE sequences')
            phase_index1 = (self.method.get('PVM_EncGenSteps1') + center[1]).astype(int)
            phase_index2 = (self.method.get('PVM_EncGenSteps2') + center[2]).astype(int)
            fid = fid.reshape((self.NR,NPE,self.NI,self.NRecs,Nreadout)).transpose(4,1,3,2,0)
            for index, (i,j) in enumerate(zip(phase_index1,phase_index2)):
                temp[readStart:,i,j,:,:,:] = fid[:,index,:,:,:]
            fid = np.zeros_like(temp)
            fid[:,:,:,:,obj_order,:] = temp
        else:
            fid = fid.reshape((self.NR,-1,self.NI,phase_factor,self.NRecs,Nreadout)).transpose(0,2,4,1,3,5)
            fid = fid.reshape((self.NR,self.NI,self.NRecs,NPE,Nreadout)).transpose((4,3,2,1,0))
            fid = fid.reshape(Nreadout, int(EncMatrix[1]), int(EncMatrix[2]) if dims == 3 else 1, self.NRecs, self.NI, self.NR, order = 'F')
            temp[readStart:,phase_encode1,:,:,:,:] = fid[:,:,phase_encode2,:,:,:]
            fid = np.zeros_like(temp)
            fid[:,:,:,:,obj_order,:] = temp

        if self.method.get('EchoAcqMode') == 'allEchoes':
            fid[:,:,:,:,1::2,:] = fid[::-1,:,:,:,1::2,:]
        
        return fid
    
    def process_kspace(self):
        kspace = self.sort_kspace()  
        if len(kspace.shape) != 6:
            return kspace
        # Shift Object
        map_index= np.reshape(np.arange(0,kspace.shape[4]*kspace.shape[5]), (kspace.shape[5], kspace.shape[4]) ).flatten()
        for NR in range(self.NR):
            for NI in range(self.NI):
                kspace[:,:,:,:,NI,NR] *= np.tile(phase_rotate(kspace[:,:,:,:,NI,NR], 
                                                              self.reco.get('RECO_rotate'),
                                                              map_index[(NI+1)*(NR+1)-1])[:,:,:,np.newaxis],
                                                 [1,1,1,self.NRecs])
        
        # Zeropad KSPACE 
        RECO_ft_size = self.reco.get('RECO_ft_size')
        newdata_dims=[1, 1, 1]
        newdata_dims[0:len(RECO_ft_size)] = RECO_ft_size
        newdata = np.zeros(shape=newdata_dims+[self.NRecs, self.NI, self.NR], dtype=complex)
        for NR in range(self.NR):
            for NI in range(self.NI):
                for chan in range(self.NRecs):
                    newdata[:,:,:,chan,NI,NR] = zero_filling(kspace[:,:,:,chan,NI,NR], RECO_ft_size).reshape(newdata[:,:,:,chan,NI,NR].shape)

        return newdata 
     
    # 4) CONVERT TO IMAGE SPACE if FULLY SAMPLED CARTESIAN
    def reconstruct(self, kspace=None, rms=True):
        if kspace == None:
            kspace = self.process_kspace()
        if len(kspace.shape) != 6:
            return kspace # sorted fid
        if self.CS:
            return kspace # zero padded kspace
        
        # Always FT and correct Phase
        image = np.fft.fftshift(np.fft.ifftn(kspace, axes=(0,1,2)), axes=(0,1,2))
        image *= np.tile(phase_corr(image)[:,:,:,np.newaxis,np.newaxis,np.newaxis],
                                          [1,1,1,self.NRecs,self.NI,self.NR])
        if rms:
            image = np.sqrt(np.mean(np.square(np.abs(image)), axis=3))
        return image
    