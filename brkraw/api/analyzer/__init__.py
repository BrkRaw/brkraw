"""Analyzer module initialization.

This module imports and exposes various analyzer classes used to parse and process
information from raw datasets into more readable formats. Each analyzer provides
specific functionalities tailored to different aspects of data processing and analysis.

Exposed Classes:
    BaseAnalyzer: Provides common features and utilities shared among all analyzers.
    ScanInfoAnalyzer: Specializes in parsing and analyzing scan information from raw datasets.
    AffineAnalyzer: Handles the computation and analysis of affine matrices from dataset parameters.
    DataArrayAnalyzer: Focuses on parsing and returning structured data arrays and related metadata.
"""

from .base import BaseAnalyzer
from .scaninfo import ScanInfoAnalyzer
from .affine import AffineAnalyzer
from .dataarray import DataArrayAnalyzer

__all__ = ['BaseAnalyzer', 'ScanInfoAnalyzer', 'AffineAnalyzer', 'DataArrayAnalyzer']