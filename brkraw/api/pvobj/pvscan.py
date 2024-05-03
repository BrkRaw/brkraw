"""Provides the PvScan class for managing individual scan data within a Paravision study.

This module includes the PvScan class, derived from BaseMethods, to manage and interact with individual 
scans and their respective reconstructions. It handles the organization, retrieval, and processing of scan-specific information, 
supporting both compressed and uncompressed data formats.

Classes:
    PvScan: Manages a single scan's dataset, organizing reconstructions and handling specific data retrieval efficiently.
"""

from __future__ import annotations
import os
from collections import OrderedDict
from .base import BaseMethods
from .pvreco import PvReco
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, Tuple, Dict
    from pathlib import Path

class PvScan(BaseMethods):
    """Represents and manages an individual scan within a Paravision study dataset.

    Inherits from BaseMethods to utilize general methods for file handling and dataset validation.
    Manages the data associated with a single scan, including various reconstructions, both compressed and uncompressed.

    Attributes:
        is_compressed (bool): Indicates whether the scan's dataset is compressed, affecting how files are accessed and processed.
        path (str): The file system path to the scan's dataset.
        avail (list): A list of IDs representing the available reconstructions within the scan.
        contents (dict): A structured dictionary representing the organized contents of the scan.

    Methods:
        update(contents): Updates the contents of the scan with new data.
        set_reco(path, reco_id, contents): Initializes a PvReco object for a specific reconstruction.
        get_reco(reco_id): Retrieves a PvReco object for a given reconstruction ID.
    """
    def __init__(self, 
                 scan_id: Optional[int], 
                 pathes: Tuple[Path, Path], 
                 contents: Optional[Dict]=None, 
                 recos: Optional[OrderedDict]=None):
        """Initializes a PvScan object with the specified scan ID, paths, and optional contents and reconstructions.

        Args:
            scan_id (int): The ID of the scan.
            pathes (tuple): A tuple containing the root path and the specific scan path.
            contents (dict, optional): The initial contents of the scan's dataset. Defaults to None.
            recos (OrderedDict, optional): A dictionary of PvReco objects. Defaults to None.

        Raises:
            FileNotFoundError: If the paths do not exist or are invalid.
            ValueError: If the paths are neither directories nor recognizable compressed file formats.
        """
        self._scan_id = scan_id
        self._rootpath = self._resolve(pathes[0])
        self._path = self._resolve(pathes[1])
        self.update(contents)
        self._recos = OrderedDict(recos) if recos else OrderedDict()
    
    def update(self, contents: Dict):
        """pdates the contents of the scan's dataset.

        Args:
            contents (dict): The new contents to update the dataset with.

        Returns:
            None
        """
        if contents:
            self.is_compressed = True if contents.get('file_indexes') else False
        self._contents = contents
    
    def set_reco(self, path: Path, reco_id: int, contents: Dict):
        """Initializes and stores a PvReco object for a specific reconstruction within the scan.

        Args:
            path (Path): The path to the reconstruction data.
            reco_id (int): The unique identifier for the reconstruction.
            contents (Dict): The data associated with the reconstruction.

        Returns:
            None
        """
        self._recos[reco_id] = PvReco(self._scan_id, reco_id, (self._rootpath, path), contents)
    
    def get_reco(self, reco_id: int):
        """Retrieves the PvReco object associated with the specified reconstruction ID.

        Args:
            reco_id (int): The ID of the reconstruction to retrieve.

        Returns:
            PvReco: The reconstruction object.

        Raises:
            KeyError: If the specified reconstruction ID does not exist within the scan.
        """
        return self._recos[reco_id]

    def get_visu_pars(self, reco_id: Optional[int] = None):
        """Retrieves visualization parameters ('visu_pars') for the scan or a specific reconstruction.

        This method attempts to find and return the 'visu_pars' file. It looks for this file in the following order:
        1. In a specific reconstruction, if `reco_id` is provided.
        2. Directly within the scan's own contents, if available.
        3. In the first available reconstruction that contains 'visu_pars'.

        Args:
            reco_id (Optional[int]): The ID of the reconstruction from which to retrieve 'visu_pars'. If None,
                                    the method searches across the scan and all its reconstructions.

        Returns:
            The visualization parameters as specified in 'visu_pars'.

        Raises:
            FileNotFoundError: If 'visu_pars' cannot be found in the specified reconstruction, within the scan,
                            or across any of the available reconstructions.
        """
        if reco_id:
            return getattr(self.get_reco(reco_id), 'visu_pars')
        elif 'visu_pars' in self.contents['files']:
            return getattr(self, 'visu_pars')
        elif len(self.avail):
            recoobjs = [self.get_reco(rid) for rid in self.avail]
            for recoobj in recoobjs:
                if 'visu_pars' in recoobj.contents['files']:
                    return getattr(recoobj, 'visu_pars')
        raise FileNotFoundError
    
    @property
    def path(self):
        """Provides the combined filesystem path of the scan's dataset.

        Returns:
            str: The full path combining the root and specific scan path.
        """
        path = (self._rootpath, self._path)
        if self.is_compressed:
            return path
        return os.path.join(*path)
    
    @property
    def avail(self):
        """Provides a list of available reconstruction IDs within the scan.

        Returns:
            list: A sorted list of available reconstruction IDs.
        """
        return sorted(list(self._recos))