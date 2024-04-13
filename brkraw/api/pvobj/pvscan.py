import os
from collections import OrderedDict
from .base import BaseMethods
from .pvreco import PvReco

class PvScan(BaseMethods):
    """
    A class representing a PvScan object.

    Inherits from BaseMethods.

    Attributes:
        is_compressed (bool): Indicates if the dataset is compressed.

    Methods:
        update(contents): Update the contents of the dataset.
        set_reco(path, reco_id, contents): Set a reco object with the specified path, ID, and contents.
        get_reco(reco_id): Get a specific reco object by ID.

    Properties:
        path (str): The path.
        avail (list): A list of available items.
        contents (dict): A dictionary of pvscan contents.
    """
    def __init__(self, scan_id, pathes, contents=None, recos=None):
        """
        Initialize a Dataset object.

        Args:
            scan_id (int): The ID of the scan.
            pathes (tuple): A tuple containing the root path and the path.
            contents (list, optional): The initial contents of the dataset. Defaults to None.
            recos (dict, optional): A dictionary of reco objects. Defaults to None.

        Attributes:
            _scan_id (int): The ID of the scan.
            _rootpath (str): The root path.
            _path (str): The path.
            _recos (OrderedDict): An ordered dictionary of reco objects.

        Methods:
            update(contents): Update the contents of the dataset.
        """
        self._scan_id = scan_id
        self._rootpath, self._path = pathes
        self.update(contents)
        self._recos = OrderedDict(recos) if recos else OrderedDict()
    
    def update(self, contents):
        """
        Update the contents of the dataset.

        Args:
            contents (list): The new contents of the dataset.

        Returns:
            None
        """
        if contents:
            self.is_compressed = True if contents.get('file_indexes') else False
        self._contents = contents
    
    def set_reco(self, path, reco_id, contents):
        """
        Set a reco object with the specified path, ID, and contents.

        Args:
            path (str): The path of the reco object.
            reco_id (int): The ID of the reco object.
            contents (list): The contents of the reco object.

        Returns:
            None
        """
        self._recos[reco_id] = PvReco(self._scan_id, reco_id, (self._rootpath, path), contents)
    
    def get_reco(self, reco_id):
        """
        Get a specific reco object by ID.

        Args:
            reco_id (int): The ID of the reco object to retrieve.

        Returns:
            object: The specified reco object.

        Raises:
            KeyError: If the specified reco ID does not exist.
        """
        return self._recos[reco_id]

    def get_visu_pars(self, reco_id=None):
        if reco_id:
            return getattr(self.get_reco(reco_id), 'visu_pars')
        elif 'visu_pars' in self.contents['files']:
            return getattr(self, 'visu_pars')
        elif len(self.avail):
            recoobj = self.get_reco(self.avail[0])
            if 'visu_pars' not in recoobj.contents['files']:
                raise FileNotFoundError
            else:
                return getattr(recoobj, 'visu_pars')
        else:
            raise FileNotFoundError
    
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
    
    @property
    def avail(self):
        """
        A property representing the available items.

        Returns:
            list: A list of available items.
        """
        return sorted(list(self._recos))