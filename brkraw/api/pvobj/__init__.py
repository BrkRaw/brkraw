"""Initialization for the pvobj module.

This module is a cornerstone for interfacing with raw datasets within the Bruker imaging framework.
It provides essential classes for parsing raw datasets, managing parameter metadata, and organizing
data at various levels—from individual scans to comprehensive experimental sessions.

Classes Exposed:
    PvStudy: Manages data for an entire session, encapsulating all scans and reconstructions.
    PvScan: Handles data related to individual scans, including raw FIDs, acquisition, and method parameters.
    PvReco: Manages data related to image reconstructions within a single scan.
    PvFiles: Provides a flexible container for raw files that may not be systematically organized,
             allowing users to add any files and utilize full module functionalities if all required files are present.
    Parameter: Represents parameter metadata for various components within a scan.
    Parser: Facilitates the parsing of raw dataset information into structured formats.
"""

from .pvstudy import PvStudy
from .pvscan import PvScan
from .pvreco import PvReco
from .pvfiles import PvFiles
from .parameters import Parameter, Parser

__all__ = ['PvStudy', 'PvScan', 'PvReco', 'PvFiles', 'Parameter', 'Parser']