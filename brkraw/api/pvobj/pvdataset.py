import re
import zipfile
from collections import OrderedDict
from pathlib import Path
from .base import BaseMethods
from .pvscan import PvScan


class PvDataset(BaseMethods):
    """
    A class representing a PvDataset object.

    Inherits from BaseMethods.

    Attributes:
        is_compressed (bool): Indicates if the dataset is compressed.

    Methods:
        get_scan(scan_id): Get a specific scan object by ID.

    Properties:
        path (str): The path of the object.
        avail (list): A list of available scans.
        contents (dict): A dictionary of pvdataset contents.
    """
    def __init__(self, path: Path, debug: bool=False):
        """
        Initialize the object with the given path and optional debug flag.

        Args:
            path: The path to initialize the object with.
            debug: A flag indicating whether debug mode is enabled.
            **kwargs: Additional keyword arguments.

        Raises:
            Any exceptions raised by _check_dataset_validity or _construct methods.

        Notes:
            If 'pvdataset' is present in kwargs, it will be used to initialize the object via super().

        Examples:
            obj = ClassName(path='/path/to/dataset', debug=True)
        """

        if not debug:    
            self._check_dataset_validity(path)
            self._construct()
    
    # internal method
    def _check_dataset_validity(self, path: Path):
        """
        Checks the validity of a given dataset path.

        Note: This method only checks the validity of the dataset to be fetched using `fetch_dir` and `fetch_zip`,
        and does not check the validity of a `PvDataset`.

        Args:
            path (str): The path to check.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path is not a directory or a file, or if it does not meet the required criteria.

        Returns:
            None
        """
        path = Path(path) if isinstance(path, str) else path
        self._path: Path = path.absolute()
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
        """
        Constructs the object by organizing the contents.

        This method constructs the object by organizing the contents based on the provided directory structure.
        It iterates over the sorted contents and updates the `_scans` and `_backup` dictionaries accordingly.
        After processing, it removes the processed paths from the `_contents` dictionary.

        Args:
            **kwargs: keyword argument for datatype specification.
        
        Returns:
            None
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
        """
        The `_process_childobj` method processes a child object based on the provided arguments and updates the internal state of the object.

        Args:
            matched: A `re.Match` object representing the matched pattern.
            item: A tuple containing the path and contents of the child object.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The path of the processed child object.

        Raises:
            None.

        Examples:
            # Example usage of _process_childobj
            matched = re.match(pattern, input_string)
            item = ('path/to/child', {'dirs': set(), 'files': [], 'file_indexes': []})
            result = obj._process_childobj(matched, item, pvscan={'binary_files': [], 'parameter_files': ['method', 'acqp', 'visu_pars']})
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
        for _, contents in super().contents.items():
            if 'subject' in contents['files']:
                return contents

    def _clear_contents(self, to_be_removed):
        for path in to_be_removed:
            try:
                del self._contents[path]
            except KeyError:
                self._dummy.append(path)

    @property
    def path(self):
        """
        Gets the path of the object.

        Returns:
            str: The path of the object.
        """
        return self._path

    @property
    def avail(self):
        """
        A property representing the available scans.

        Returns:
            list: A list of available scans.
        """
        return sorted(list(self._scans))
    
    def get_scan(self, scan_id):
        """
        Get a specific scan object by ID.

        Args:
            scan_id (int): The ID of the scan object to retrieve.

        Returns:
            object: The specified scan object.

        Raises:
            KeyError: If the specified scan ID does not exist.
        """
        return self._scans[scan_id]
    
    def __dir__(self):
        return super().__dir__() + ['path', 'avail', 'get_scan']
