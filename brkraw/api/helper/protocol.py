from __future__ import annotations
from typing import TYPE_CHECKING
from .base import BaseHelper
if TYPE_CHECKING:
    from ..analyzer import ScanInfoAnalyzer

class Protocol(BaseHelper):
    """_summary_
    Helper class to parse protocol parameters for data acqusition form 'acqp' file

    Args:
        BaseHelper (_type_): _description_
    """
    def __init__(self, analobj: 'ScanInfoAnalyzer'):
        super().__init__()
        
        acqp = analobj.acqp
        if not acqp:
            self._warn("Failed to fetch all Protocol information because the 'acqp' file is missing from 'analobj'.")
        self.sw_version = str(acqp.get('ACQ_sw_version')) if acqp else None
        self.operator = acqp.get('ACQ_operator') if acqp else None
        self.pulse_program = acqp.get('PULPROG') if acqp else None
        self.nucleus = acqp.get('NUCLEUS') if acqp else None
        self.protocol_name = acqp.get('ACQ_protocol_name') or acqp.get('ACQ_scan_name') if acqp else None
        self.scan_method = acqp.get('ACQ_method') if acqp else None
        self.subject_pos = acqp.get('ACQ_patient_pos') if acqp else None
        self.institution = acqp.get('ACQ_institution') if acqp else None
        self.device = acqp.get('ACQ_station') if acqp else None
            
    def get_info(self):
        return {
            'sw_version': self.sw_version,
            'operator': self.operator,
            'institution': self.institution,
            'device': self.device,
            'nucleus': self.nucleus,
            'subject_pos': self.subject_pos,
            'pulse_program': self.pulse_program,
            'protocol_name': self.protocol_name,
            'scan_method': self.scan_method,
            'warns': self.warns
        }