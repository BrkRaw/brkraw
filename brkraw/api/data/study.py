"""This module provides classes and functions for managing and analyzing MRI study data.

The primary class, Study, extends the functionalities of PvStudy from the brkraw.api.pvobj module
and integrates additional analysis capabilities through the BaseAnalyzer class. It handles the
processing of study-specific data, including the retrieval and management of scan objects,
parsing of study header information, and compiling comprehensive information about studies.

Classes:
    Study: Manages MRI study operations and integrates data processing and analysis capabilities.
           It provides methods to retrieve specific scans, parse and access study header data,
           and compile detailed information about the study and its associated scans and reconstructions.

Dependencies:
    PvStudy (from brkraw.api.pvobj): 
        Base class for handling the basic operations related to photovoltaic studies.
    BaseAnalyzer (from brkraw.api.analyzer.base): 
        Base class providing analytical methods used across different types of data analyses.
    Scan (from .scan): 
        Class representing individual scans within a study, providing detailed data access and manipulation.
    Recipe (from brkraw.api.helper.recipe): 
        Utility class used for applying specified recipes to data objects, enabling structured data extraction and analysis.

This module is utilized in MRI research environments where detailed and structured analysis of photovoltaic data is required.
"""

from __future__ import annotations
import os
import yaml
import warnings
from copy import copy
from pathlib import Path
from dataclasses import dataclass
from .scan import Scan
from brkraw.api.pvobj import PvStudy
from brkraw.api.analyzer.base import BaseAnalyzer
from brkraw.api.helper.recipe import Recipe
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional


@dataclass
class StudyHeader:
    header: dict
    scans: list
    
    
@dataclass
class ScanHeader:
    scan_id: int
    header: dict
    recos: list
    
    
@dataclass
class RecoHeader:
    reco_id: int
    header: dict
    

class Study(PvStudy, BaseAnalyzer):
    """Handles operations related to a specific study, integrating PvStudy and analytical capabilities.

    This class extends the functionalities of PvStudy to include detailed analyses
    and operations specific to the study being handled. It integrates with various 
    data processing and analysis methods defined in the base analyzer.

    Attributes:
        header (Optional[dict]): Parsed study header information.
    """
    _info: StudyHeader
    
    def __init__(self, path: Path) -> None:
        """Initializes the Study object with a specified path.

        Args:
            path (Path): The file system path to the study data.
        """
        super().__init__(self._resolve(path))
        self._parse_header()
        
    def get_scan(self,
                 scan_id: int,
                 reco_id: Optional[int] = None,
                 debug: bool = False) -> 'Scan':
        """Retrieves a Scan object for a given scan ID with optional reconstruction ID.

        Args:
            scan_id (int): The unique identifier for the scan.
            reco_id (Optional[int]): The reconstruction identifier, defaults to None.
            debug (bool): Flag to enable debugging outputs, defaults to False.

        Returns:
            Scan: The Scan object corresponding to the specified scan_id and reco_id.
        """
        pvscan = super().get_scan(scan_id)
        return Scan(pvobj=pvscan,
                    reco_id=reco_id,
                    study_address=id(self),
                    debug=debug)
    
    def _parse_header(self) -> None:
        """Parses the header information from the study metadata.

        Extracts the header data based on subject and parameters, setting up the
        study header attribute. This method handles cases with different versions
        of ParaVision by adjusting the header format accordingly.
        """
        if not self.contents or 'subject' not in self.contents['files']:
            self.header = None
            return
        subj = self.subject
        subj_header = getattr(subj, 'header') if subj.is_parameter() else None
        if title := subj_header['TITLE'] if subj_header else None:
            self.header = {k.replace("SUBJECT_", ""): v for k, v in subj.parameters.items() if k.startswith("SUBJECT")}
            self.header['sw_version'] = title.split(',')[-1].strip() if 'ParaVision' in title else "ParaVision < 6"
    
    @property
    def avail(self) -> list:
        """List of available scan IDs within the study.

        Returns:
            list: A list of integers representing the available scan IDs.
        """
        return super().avail

    @property
    def info(self) -> dict:
        if not hasattr(self, '_info'):
            self._process_header()
        if not hasattr(self, '_streamed_info'): 
            self._streamed_info = self._stream_info() 
        return self._streamed_info
    
    def _stream_info(self):
        stream = copy(self._info.__dict__)
        scans = {}
        for s in self._info.scans:
            scans[s.scan_id] = s.header
            recos = {}
            for r in s.recos:
                recos[r.reco_id] = r.header
            if recos:
                scans[s.scan_id]['recos'] = recos
        stream['scans'] = scans
        return stream
    
    def _process_header(self):
        """Compiles comprehensive information about the study, including header details and scans.

        Uses external YAML configuration to drive the synthesis of structured information about the study,
        integrating data from various scans and their respective reconstructions.

        Returns:
            dict: A dictionary containing structured information about the study, its scans, and reconstructions.
        """
        spec_path = os.path.join(os.path.dirname(__file__), 'study.yaml')
        with open(spec_path, 'r') as f:
            spec = yaml.safe_load(f)
        self._info = StudyHeader(header=Recipe(self, copy(spec)['study']).get(), scans=[])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for scan_id in self.avail:
                scanobj = self.get_scan(scan_id)
                scan_spec = copy(spec)['scan']
                scan_header = ScanHeader(scan_id=scan_id, header=Recipe(scanobj.info, scan_spec).get(), recos=[])
                for reco_id in scanobj.avail:
                    recoinfo = scanobj.get_scaninfo(reco_id)
                    reco_spec = copy(spec)['reco']
                    reco_header = Recipe(recoinfo, reco_spec).get()
                    reco_header = RecoHeader(reco_id=reco_id, header=reco_header) if reco_header else None
                    if reco_header:
                        scan_header.recos.append(reco_header)
                self._info.scans.append(scan_header)
