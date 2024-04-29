from __future__ import annotations
from ..pvobj import PvDataset
from .scan import Scan
from pathlib import Path

class Study(PvDataset):
    def __init__(self, path: Path):
        super().__init__(path)
        self._parse_header()
        
    def get_scan(self, scan_id, reco_id=None, debug=False):
        """
        Get a scan object by scan ID.
        """
        pvscan = super().get_scan(scan_id)
        return Scan(pvobj=pvscan, reco_id=reco_id, 
                    study_address=id(self), debug=debug)
    
    def _parse_header(self):
        if not self.contents or 'subject' not in self.contents['files']:
            self.header = None
            return
        subj = self.subject
        subj_header = getattr(subj, 'header') if subj.is_parameter() else None
        if title := subj_header['TITLE'] if subj_header else None:
            self.header = {k.replace("SUBJECT_",""):v for k, v in subj.parameters.items() if k.startswith("SUBJECT")}
            self.header['sw_version'] = title.split(',')[-1].strip() if 'ParaVision' in title else "ParaVision < 6"
    
    @property
    def avail(self):
        return super().avail

    @property #TODO
    def info(self):
        """output all analyzed information"""
        info = {'header': None,
                'scans': {}}
        if header := self.header:
            info['header'] = header
        # for scan_id in self.avail:
        #     scanobj = self.get_scan(scan_id)
        #     info['scans'][scan_id] = {'protocol_name': scanobj.info.protocol['protocol_name'],
        #                               'recos': {}}
        #     for reco_id in scanobj.avail:
        #         info['scans'][scan_id]['recos'][reco_id] = scanobj.get_info(reco_id).frame_group
        return info
