"""This module provides classes and functions for handling and analyzing photovoltaic objects from MRI scans.

It is designed to interface with the ParaVision data structures (`PvScan`, `PvReco`, `PvFiles`)
and perform various analytical tasks to assist in the study of MRI scans.

Classes:
    ScanInfo: Handles basic scan information and warning accumulation.
    Scan: Main interface class for working with Pv objects and handling detailed scan analysis,
          including retrieval of objects from memory and performing affine and data array analysis.

This module is part of the `brkraw` package which aims to provide tools for MRI data manipulation and analysis.
"""

from __future__ import annotations
import ctypes
from brkraw.api.pvobj import PvScan, PvReco, PvFiles
from brkraw.api.pvobj.base import BaseBufferHandler
from brkraw.api.analyzer import ScanInfoAnalyzer, AffineAnalyzer, DataArrayAnalyzer, BaseAnalyzer
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, Union
    from .study import Study


class ScanInfo(BaseAnalyzer):
    """Handles the accumulation of warnings and basic information about MRI scans.
    
    This class is designed to store general scan information and accumulate any warnings that might arise 
    during the scan processing. It serves as a foundational class for more detailed analysis classes 
    that may require access to accumulated warnings and basic scan metrics.

    Attributes:
        warns (list): A list that accumulates warning messages related to the scan analysis.
    """
    def __init__(self) -> None:
        """Initializes a new instance of ScanInfo with an empty list for warnings."""
        self.warns: list[str] = []

    @property
    def num_warns(self) -> int:
        """Counts the number of warnings accumulated during the scan processing.

        Returns:
            int: The total number of warnings accumulated.
        """
        return len(self.warns)
    

class Scan(BaseBufferHandler):
    """Interface class for working with various Pv objects and handling scan information.

    Attributes:
        pvobj (Union['PvScan', 'PvReco', 'PvFiles']): The photovoltaic object associated with this scan.
        reco_id (Optional[int]): The reconstruction ID for the scan, defaults to None.
        study_address (Optional[int]): Memory address of the study object, defaults to None.
        debug (bool): Flag to enable debug mode, defaults to False.
    """
    def __init__(self, pvobj: Union['PvScan', 'PvReco', 'PvFiles'],
                 reco_id: Optional[int] = None,
                 study_address: Optional[int] = None,
                 debug: bool = False) -> None:
        """Initializes the Scan object with necessary identifiers and addresses.

        Args:
            pvobj: The ParaVision data object to be used throughout the scan analysis.
            reco_id: Optional reconstruction identifier.
            study_address: Optional memory address of the associated study object.
            debug: Flag indicating whether to run in debug mode.
        """
        self.reco_id = reco_id
        self._study_address = study_address
        self._pvobj_address = id(pvobj)
        self.is_debug = debug
        self.set_scaninfo()
        
    def retrieve_pvobj(self) -> Union['PvScan', 'PvReco', 'PvFiles', None]:
        """Retrieves the pvobj from memory using its stored address.

        Returns:
            The pvobj if available; otherwise, None.
        """
        if self._pvobj_address:
            return ctypes.cast(self._pvobj_address,
                               ctypes.py_object).value
        return None
    
    def retrieve_study(self) -> Optional['Study']:
        """Retrieves the study object from memory using its stored address.

        Returns:
            The study object if available; otherwise, None.
        """
        if self._study_address:
            return ctypes.cast(self._study_address,
                               ctypes.py_object).value
        return None
    
    def set_scaninfo(self, reco_id: Optional[int] = None) -> None:
        """Sets the scan information based on the reconstruction ID.

        Args:
            reco_id: Optional reconstruction ID to specify which scan information to retrieve and set.
        """
        reco_id = reco_id or self.reco_id
        self.info = self.get_scaninfo(reco_id)
                
    def get_scaninfo(self,
                     reco_id: Optional[int] = None,
                     get_analyzer: bool = False) -> Union['ScanInfoAnalyzer', 'ScanInfo']:
        """Gets the scan information, optionally using an analyzer to enrich the data.

        Args:
            reco_id: Optional reconstruction ID to specify which scan information to retrieve.
            get_analyzer: Flag indicating whether to use the ScanInfoAnalyzer for detailed analysis.

        Returns:
            An instance of ScanInfo or ScanInfoAnalyzer with the relevant scan details.
        """
        infoobj = ScanInfo()
        pvobj = self.retrieve_pvobj()
        analysed = ScanInfoAnalyzer(pvobj=pvobj,  # type: ignore
                                    reco_id=reco_id, 
                                    debug=self.is_debug)
        
        if get_analyzer:
            return analysed
        for attr_name in dir(analysed):
            if 'info_' in attr_name:
                attr_vals = getattr(analysed, attr_name)
                if warns := attr_vals.pop('warns', None):
                    infoobj.warns.extend(warns)
                setattr(infoobj, attr_name.replace('info_', ''), attr_vals)
        return infoobj
    
    def get_affine_analyzer(self,
                            reco_id: Optional[int] = None) -> 'AffineAnalyzer':
        """Retrieves the affine analysis object for the specified reconstruction ID.

        Args:
            reco_id: Optional reconstruction ID to specify which affine analysis to retrieve.

        Returns:
            An AffineAnalyzer object initialized with the scan information.
        """
        if reco_id:
            info = self.get_scaninfo(reco_id, get_analyzer=False)
        else:
            info = self.info if hasattr(self, 'info') else self.get_scaninfo(self.reco_id)
        return AffineAnalyzer(info)  # type: ignore
    
    def get_datarray_analyzer(self,
                              reco_id: Optional[int] = None) -> 'DataArrayAnalyzer':
        """Retrieves the data array analyzer for the specified reconstruction ID.

        Args:
            reco_id: Optional reconstruction ID to specify which data array analysis to perform.

        Returns:
            A DataArrayAnalyzer object initialized with the scan and file information.
        """
        reco_id = reco_id or self.reco_id
        pvobj = self.retrieve_pvobj()
        fileobj = pvobj.get_2dseq(reco_id=reco_id)  # type: ignore
        self._buffers.append
        info = self.info if hasattr(self, 'info') else self.get_scaninfo(reco_id)
        return DataArrayAnalyzer(info, fileobj)  # type: ignore
    
    @property
    def avail(self) -> list[int]:
        """List of available reconstruction IDs for the current pvobj.

        Returns:
            A list of integers representing the available reconstruction IDs.
        """
        return self.pvobj.avail
    
    @property
    def pvobj(self) -> Union['PvScan', 'PvReco', 'PvFiles']:
        """Retrieves the pvobj from memory.

        Returns:
            The current bound pvobj.
        """
        return self.retrieve_pvobj()  # type: ignore
    
    @property
    def about_scan(self) -> dict:
        """Provides a dictionary with analyzed results for the scan.

        Returns:
            A dictionary containing analyzed scan results.
        """
        return self.info.to_dict()
    
    @property
    def about_affine(self) -> dict:
        """Provides a dictionary with analyzed results for affine transformations.

        Returns:
            A dictionary containing analyzed affine results.
        """
        return self.get_affine_analyzer().to_dict()
    
    @property
    def about_dataarray(self) -> dict:
        """Provides a dictionary with analyzed results for the data array.

        Returns:
            A dictionary containing analyzed data array results.
        """
        return self.get_datarray_analyzer().to_dict()
