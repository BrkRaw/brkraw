"""Initializes and exports the main components of the MRI study and scan management package.

This package module consolidates and provides easy access to the primary classes involved in managing
and analyzing MRI study and scan data. The classes exported here facilitate the interfacing with MRI
data at both the study and scan levels, supporting detailed data manipulation and analysis.

Exports:
    Study: A class that manages MRI study operations, extending functionalities for detailed study data handling.
    Scan: A class representing individual MRI scans, capable of detailed scan data analysis and management.
    ScanInfo: A class for managing basic information and warnings related to MRI scans.

The `__init__.py` module ensures that these classes are readily accessible when the package is imported,
making the package easier to use and integrate into larger projects or applications.

Example:
    from your_package_name import Study, Scan, ScanInfo

This enables straightforward access to these classes for further development and deployment in MRI data analysis tasks.
"""

from .study import Study
from .scan import Scan, ScanInfo

__all__ = ['Study', 'Scan', 'ScanInfo']
