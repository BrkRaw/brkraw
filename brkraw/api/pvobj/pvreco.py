"""Module providing the PvReco class, a component of Paravision Objects.

The PvReco class is designed to manage individual reconstructions within a scan from Paravision datasets. 
It extends the BaseMethods class to incorporate more specific functionalities such as managing compressed data formats and 
directly handling the file paths and contents of reconstruction data.
The class is particularly geared towards handling the details at the reconstruction level, enabling detailed management and 
access to specific types of imaging data. It includes functionalities to initialize reconstructions, update their contents, 
and provide access paths, ensuring that data can be accessed and manipulated efficiently and effectively.

Classes:
    PvReco: Manages the data and processes related to individual reconstructions within a Paravision scan, providing tools 
            to handle and organize the specific data associated with those reconstructions.
"""

from __future__ import annotations
import os
import warnings
from .base import BaseMethods
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Tuple, Dict
    from typing import Optional
    from pathlib import Path


class PvReco(BaseMethods):
    """Manages the reconstruction-specific data within a scan in a Paravision study.

    This class extends `BaseMethods` to provide specialized handling of the data associated with a particular
    reconstruction. It supports both compressed and uncompressed data formats and provides utilities to manage
    and access reconstruction-specific details.

    Attributes:
        is_compressed (bool): Indicates whether the dataset is compressed, affecting how files are accessed and processed.
        path (str): The file system path to the reconstruction's data.
        scan_id (int): Identifier for the scan associated with this reconstruction.
        reco_id (int): Identifier for this specific reconstruction.
    
    Args:
        scan_id (int): The ID of the scan.
        reco_id (int): The ID of the reconstruction.
        pathes (Tuple[Path, Path]): Contains the root path and specific reconstruction path.
        contents (Optional[Dict], optional): Initial content data for the reconstruction.
    """
    def __init__(self, scan_id: int, reco_id: int, pathes: Tuple['Path', 'Path'], 
                 contents: Optional['Dict']=None):
        """Initializes the PvReco object with specified identifiers, paths, and optional contents.

        Args:
            scan_id (int): The identifier of the scan to which this reconstruction belongs.
            reco_id (int): The unique identifier for this reconstruction within its scan.
            pathes (Tuple[Path, Path]): A tuple containing the root path and the specific path for this reconstruction.
            contents (Dict, optional): A dictionary representing the initial contents of the reconstruction.

        Raises:
            FileNotFoundError: If the provided paths do not exist or are not accessible.
            ValueError: If the paths provided do not lead to expected data formats or locations.
        """
        self._scan_id = scan_id
        self._reco_id = reco_id
        self._rootpath = self._resolve(pathes[0])
        self._path = self._resolve(pathes[1])
        self._contents = contents
        self.is_compressed = True if contents.get('file_indexes') else False
            
    @property
    def path(self):
        """Constructs and returns the full filesystem path for this reconstruction.

        If the reconstruction data is compressed, this returns a tuple of paths; otherwise,
        it combines them into a single filesystem path.

        Returns:
            Union[Tuple[Path, Path], str]: The full path or paths to the reconstruction data.
        """
        path = (self._rootpath, self._path)
        if self.is_compressed:
            return path
        return os.path.join(*path)

    def get_fid(self):
        """Issues a warning that the 'get_fid' method is not supported for PvReco objects.

        This method is typically used at the scan or study level, not at the reconstruction level.

        Returns:
            None

        Raises:
            Warning: Always warns that the method is not applicable for PvReco objects.
        """
        warnings.warn(f'{self.__class__} does not support get_fid method. use Scan- or Study-level object instead')
        return None