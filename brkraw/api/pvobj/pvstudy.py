"""Provides the PvStudy class, which serves as a comprehensive handler for entire Paravision study datasets.

This module includes the PvStudy class, derived from BaseMethods, to manage and interact with datasets that may
include multiple scans and various data types, both compressed and uncompressed. It facilitates the organization,
retrieval, and processing of study-specific information and individual scans, enhancing the handling of complex
imaging data.

Classes:
    PvStudy: Manages an entire study's dataset, organizing scans and handling specific data retrieval efficiently.
"""

from __future__ import annotations
import re
import zipfile
from collections import OrderedDict
from .base import BaseMethods
from .pvscan import PvScan
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pathlib import Path


class PvStudy(BaseMethods):
    """Represents and manages an entire Paravision study dataset.

    Inherits from BaseMethods to utilize general methods for file handling and dataset validation.
    Manages multiple scans and their respective data, supporting both compressed and uncompressed formats.

    Attributes:
        is_compressed (bool): Indicates whether the dataset is compressed, affecting how files are accessed and processed.
        path (str): The file system path to the study dataset.
        avail (list): A list of IDs representing the available scans within the dataset.
        contents (dict): A structured dictionary representing the organized contents of the dataset.

    Methods:
        get_scan(scan_id): Retrieves a PvScan object for a given scan ID, facilitating detailed access to specific scans.
    """
    def __init__(self, path: Path, debug: bool=False):
        """Initializes a PvStudy object with the specified path and debug settings.

        Args:
            path (Path): The filesystem path to the dataset.
            debug (bool, optional): If set to True, enables debug mode which may affect logging and error reporting.

        Raises:
            FileNotFoundError: If the path does not exist or is invalid.
            ValueError: If the path is neither a directory nor a recognizable compressed file format.
        """
        if not debug:    
            self._check_dataset_validity(self._resolve(path))
            self._construct()
    
    # internal method
    def _check_dataset_validity(self, path: Path):
        """Validates the provided path to ensure it points to a viable dataset.

        Args:
            path (Path): The path to validate.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path is neither a directory nor a valid compressed file.
        """
        self._path = path
        if not self._path.exists():
            raise FileNotFoundError(f"The path '{self._path}' does not exist.")
        if self._path.is_dir():
            self._contents = self._fetch_dir(self._path)
            self.is_compressed = False
        elif self._path.is_file() and zipfile.is_zipfile(self._path):
            self._contents = self._fetch_zip(self._path)
            self.is_compressed = True
        else:
            raise ValueError(f"The path '{self._path}' does not meet the required criteria.")
    
    def _construct(self):
        """Organizes the dataset contents by parsing directories and files, structuring them for easy access.

        Processes directories to segregate scans and their respective data, handling both uncompressed and compressed datasets.
        """
        self._scans = OrderedDict()
        self._backup = OrderedDict()

        to_remove = []
        for path, contents in self._contents.items():
            if not path:
                self._root = contents
                to_remove.append(path)
            elif not contents['files']:
                to_remove.append(path)
            elif matched := re.match(r'(?:.*/)?(\d+)/(\D+)/(\d+)$', path) or re.match(r'(?:.*/)?(\d+)$', path):
                to_remove.append(self._process_childobj(matched, (path, contents)))
        self._clear_contents(to_remove)

    def _process_childobj(self, matched, item):
        """The `_process_childobj` method processes a child object based on the provided arguments and updates the internal state of the object.

        Args:
            matched: A `re.Match` object representing the matched pattern.
            item: A tuple containing the path and contents of the child object.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The path of the processed child object.
        """
        path, contents = item
        scan_id = int(matched.group(1))
        if scan_id not in self._scans:
            self._scans[scan_id] = PvScan(scan_id, (self.path, path))
        if len(matched.groups()) == 1 and 'pdata' in contents['dirs']:
            self._scans[scan_id].update(contents)
        elif len(matched.groups()) == 3 and matched.group(2) == 'pdata':
            reco_id = int(matched.group(3))
            self._scans[scan_id].set_reco(path, reco_id, contents)
        else:
            self._backup[path] = contents
        return path

    @property
    def contents(self):
        """Retrieves the contents of the study that include 'subject' in their files list.

        This property filters the study's dataset contents, returning only those parts of the dataset
        where the 'subject' file is present, which is typically critical for study-specific information.

        Returns:
            dict: The dictionary of contents that includes 'subject' among its files.
        """
        for _, contents in super().contents.items():
            if 'subject' in contents['files']:
                return contents

    def _clear_contents(self, to_be_removed):
        """Clears specified contents from the dataset's memory structure.

        This method attempts to remove paths listed in `to_be_removed` from the dataset's content dictionary.
        If a path cannot be found (i.e., it's already been removed or never existed), it logs the path to `_dummy`
        for further debugging or inspection.

        Args:
            to_be_removed (list): A list of paths to be removed from the dataset's contents.

        Returns:
            None
        
        Notes:
            The `_dummy` list can be used to track removal errors or inconsistencies in the dataset's path management.
        """
        for path in to_be_removed:
            try:
                del self._contents[path]
            except KeyError:
                self._dummy.append(path)

    @property
    def path(self):
        """Returns the filesystem path of the study dataset.

        Returns:
            str: The path to the dataset.
        """
        return self._path

    @property
    def avail(self):
        """Provides a list of available scan IDs within the dataset.

        Returns:
            list: A sorted list of available scan IDs.
        """
        return sorted(list(self._scans))
    
    def get_scan(self, scan_id: int):
        """Retrieves the scan object associated with the specified scan ID.

        Args:
            scan_id (int): The unique identifier for the scan.

        Returns:
            PvScan: The scan object associated with the given ID.

        Raises:
            KeyError: If there is no scan associated with the provided ID.
        """
        return self._scans[scan_id]
    
    def __dir__(self):
        """Customizes the directory listing to include specific attributes and methods.

        Returns:
            list: A list of attribute names and methods available in this object.
        """
        return super().__dir__() + ['path', 'avail', 'get_scan']
