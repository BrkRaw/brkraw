from __future__ import annotations
import sys
import ctypes
from typing import Dict
from .analyzer import ScanInfoAnalyzer, AffineAnalyzer, DataArrayAnalyzer
from ..config import ConfigManager
from .pvobj import PvDataset, PvScan


class BrukerLoader(PvDataset):
    def __init__(self, path):
        super().__init__(path, **ConfigManager().get('spec'))
        self._parse_header()
        
    def get_scan(self, scan_id, reco_id=None, analyze=True):
        """
        Get a scan object by scan ID.
        """
        pvscan = super().get_scan(scan_id)
        return ScanObj(pvscan=pvscan, reco_id=reco_id, 
                       loader_address=id(self), analyze=analyze)
    
    def _parse_header(self) -> (Dict | None):
        if not len(self._contents.keys()):
            self.header = None
            return
        contents = self._contents if 'files' in self._contents else self._contents[list(self._contents.keys())[0]]
        if subj := getattr(self, 'subject') if 'subject' in contents['files'] else None:
            subj_header = getattr(subj, 'header') if subj else None
            if title := subj_header['TITLE'] if subj_header else None:
                pvspec = title.split(',')[-1].strip() if 'ParaVision' in title else "ParaVision < 6"
                if "360" in title:
                    entry, position = getattr(subj, "SUBJECT_study_instrument_position").split('_')[:2]
                else:
                    entry = getattr(subj, "SUBJECT_entry").split('_')[-1]
                    position = getattr(subj, "SUBJECT_position").split('_')[-1]

            self.header = {
                'version': pvspec,
                'user_account': subj_header['OWNER'],
                'subject_entry': entry,
                'subject_position': position,
            }
        else:
            self.header = None
    
    def info(self, io_handler=None):
        io_handler = io_handler or sys.stdout
        

class ScanInfo:
    def __init__(self):
        pass

class ScanObj(PvScan):
    def __init__(self, pvscan: 'PvScan', reco_id: int|None = None,
                 loader_address: int|None = None, analyze: bool=True):
        super().__init__(pvscan._scan_id, 
                         (pvscan._rootpath, pvscan._path), 
                         pvscan._contents, 
                         pvscan._recos, 
                         binary_files = pvscan._binary_files, 
                         parameter_files = pvscan._parameter_files)
        
        self.reco_id = reco_id
        self._loader_address = loader_address
        self._pvscan_address = id(pvscan)
        if analyze:
            self.set_info()
    
    def set_info(self):
        self.info = self.get_info(self.reco_id)
                
    def get_info(self, reco_id):
        infoobj = ScanInfo()
        
        pvscan = self.retrieve_pvscan()
        analysed = ScanInfoAnalyzer(pvscan, reco_id)
        for attr_name in dir(analysed):
            if 'info_' in attr_name:
                attr_vals = getattr(analysed, attr_name)
                setattr(infoobj, attr_name.replace('info_', ''), attr_vals)
        return infoobj
    
    def get_affine(self, subj_type:str|None = None, subj_position:str|None = None, get_analyzer=False):
        info = self.info if hasattr(self, 'info') else self.get_info(self.reco_id)
        analyzer = AffineAnalyzer(info)
        return analyzer if get_analyzer else analyzer.get_affine(subj_type, subj_position)
    
    def get_dataarray(self, reco_id: int|None = None, get_analyzer=False):
        reco_id = reco_id or self.avail[0]
        recoobj = self.get_reco(reco_id)
        datafiles = [f for f in recoobj._contents['files'] if f in recoobj._binary_files]
        if not len(datafiles):
            raise FileNotFoundError('no binary file')
        fileobj = recoobj._open_as_fileobject(datafiles.pop())
        info = self.info if hasattr(self, 'info') else self.get_info(self.reco_id)
        analyzer = DataArrayAnalyzer(info, fileobj)
        return analyzer if get_analyzer else analyzer.get_dataarray()
    
    def retrieve_pvscan(self):
        if self._pvscan_address:
            return ctypes.cast(self._pvscan_address, ctypes.py_object).value
    
    def retrieve_loader(self):
        if self._loader_address:
            return ctypes.cast(self._loader_address, ctypes.py_object).value
        