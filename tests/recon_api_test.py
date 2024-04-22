from brkraw.app import tonifti as tonii
from brkraw.lib.recon import reconstruction

import numpy as np
import matplotlib.pyplot as plt

import nibabel as nib

fiddata_path = 'YOUR.PvDatasets'
studyobj = tonii.brkraw.BrkrawToNifti(fiddata_path)
scan_id  = 10 # REPLACE WITH YOUR SCAN NUMBER
reco_id  = 1
scanobj  = studyobj.get_scan(scan_id)

reconobj = np.abs(np.squeeze(reconstruction(scanobj, rms=True)))
affine   = studyobj.get_affine(scan_id, reco_id)
dataobj  = studyobj.get_dataobj(scan_id, reco_id)

print(reconobj.shape)
plt.subplot(1,2,1)
if len(reconobj.shape) == 2:
    plt.imshow(reconobj[:,:].T)
    plt.title(f"{scan_id},{scanobj.acqp['ACQ_scan_name']}")
elif len(reconobj.shape) == 3:
    plt.imshow(reconobj[:,:,reconobj.shape[2]//2].T)
    plt.title(f"{scan_id},{scanobj.acqp['ACQ_scan_name']}")
elif len(reconobj.shape) == 4:
    plt.imshow(reconobj[:,:,reconobj.shape[2]//2,0].T)
    plt.title(f"{scan_id},{scanobj.acqp['ACQ_scan_name']}")  
plt.subplot(1,2,2)
if len(reconobj.shape) == 2:
    plt.imshow(dataobj[:,:].T)
    plt.title(f"{scan_id},dataobj")
elif len(reconobj.shape) == 3:
    plt.imshow(dataobj[:,:,dataobj.shape[2]//2].T)
    plt.title(f"{scan_id},dataobj")
elif len(reconobj.shape) == 4:
    plt.imshow(dataobj[:,:,dataobj.shape[2]//2,0].T)
    plt.title(f"{scan_id},dataobj")  
plt.show()

print(reconobj.shape, dataobj.shape) 
assert np.prod(dataobj.shape) == np.prod(reconobj.shape), "Shape mismatched"

niiobj = nib.Nifti1Image(reconobj/np.max(np.abs(reconobj)), affine)
niiobj.to_filename('reconfile.nii.gz')
