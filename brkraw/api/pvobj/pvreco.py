import os
import warnings
from .base import BaseMethods


class PvReco(BaseMethods):
    """
    A class representing a PvReco object.

    Inherits from BaseMethods.
    
    Attributes:
        is_compressed (bool): Indicates if the dataset is compressed.

    Args:
        scan_id (int): The ID of the scan.
        reco_id (int): The ID of the reconstruction.
        pathes (tuple): A tuple containing the root path and the path.
        contents (list): A list of contents.

    Properties:
        path (str): The path.
    """
    def __init__(self, scan_id, reco_id, pathes, contents):
        """
        Initialize a Dataset object.

        Args:
            scan_id (int): The ID of the scan.
            reco_id (int): The ID of the reconstruction.
            pathes (tuple): A tuple containing the root path and the path.
            contents (list): A list of contents.

        Attributes:
            _scan_id (int): The ID of the scan.
            _reco_id (int): The ID of the reconstruction.
            _rootpath (str): The root path.
            _path (str): The path.
            _contents (list): The list of contents.
        """
        self._scan_id = scan_id
        self._reco_id = reco_id
        self._rootpath, self._path = pathes
        self._contents = contents
        self.is_compressed = True if contents.get('file_indexes') else False
            
    @property
    def path(self):
        """
        A property representing the path.

        Returns:
            str: The path.
        """
        path = (self._rootpath, self._path)
        if self.is_compressed:
            return path
        return os.path.join(*path)

    def get_fid(self):
        warnings.warn(f'{self.__class__} does not support get_fid method. use Scan- or Study-level object instead')
        return None