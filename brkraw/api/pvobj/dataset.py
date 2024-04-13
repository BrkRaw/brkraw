import os
import re
import zipfile
from collections import OrderedDict
from collections import defaultdict
from .parser import Parameter


class BaseMethods:
    """
    The `BaseMethods` class provides internal method for PvObjects.

    Explanation:
    This class contains various methods for handling files and directories, including fetching directory structure, 
    fetching zip file contents, opening files as file objects or strings, retrieving values associated with keys, and setting configuration options.

    Args:
        **kwargs: Keyword arguments for configuration options.
        
    Returns:
        None
    """
    _scan_id = None
    _reco_id = None
    _path = None
    _rootpath = None
    _contents = None
    
    @staticmethod
    def _fetch_dir(path):
        """Searches for directories and files in a given directory and returns the directory structure.

        Args:
            path: The path to the directory.

        Returns:
            dict: A dictionary representing the directory structure.
                The keys are the relative paths of the directories, and the values are dictionaries with the following keys:
                - 'dirs': A list of directory names.
                - 'files': A list of file names.
                - 'file_indexes': An empty list.
        """
        contents = OrderedDict()
        abspath = os.path.abspath(path)
        for dirpath, dirnames, filenames in os.walk(abspath):
            normalized_dirpath = os.path.normpath(dirpath)
            relative_path = os.path.relpath(normalized_dirpath, abspath)
            contents[relative_path] = {'dirs': dirnames, 'files': filenames, 'file_indexes': []}
        return contents
    
    @staticmethod
    def _fetch_zip(path):
        """Searches for files in a zip file and returns the directory structure and file information.

        Args:
            path: The path to the zip file.

        Returns:
            dict: A dictionary representing the directory structure and file information.
                The keys are the directory paths, and the values are dictionaries with the following keys:
                - 'dirs': A set of directory names.
                - 'files': A list of file names.
                - 'file_indexes': A list of file indexes.
        """
        with zipfile.ZipFile(path) as zip_file:
            contents = defaultdict(lambda: {'dirs': set(), 'files': [], 'file_indexes': []})
            for i, item in enumerate(zip_file.infolist()):
                if not item.is_dir():
                    dirpath, filename = os.path.split(item.filename)
                    contents[dirpath]['files'].append(filename)
                    contents[dirpath]['file_indexes'].append(i)
                    while dirpath:
                        dirpath, dirname = os.path.split(dirpath)
                        if dirname:
                            contents[dirpath]['dirs'].add(dirname)
        return contents
    
    def _open_as_fileobject(self, key):
        """Opens a file object for the given key.

        Args:
            key: The key to identify the file.

        Returns:
            file object: The opened file object.

        Raises:
            ValueError: If the key does not exist in the files.
        """
        rootpath = self._rootpath or self._path
        if not self.contents:
            raise ValueError(f'file not exists in "{rel_path}".')
        files = self.contents.get('files')
        path_list = [*([str(self._scan_id)] if self._scan_id else []), *(['pdata', str(self._reco_id)] if self._reco_id else []), key]

        if key not in files:
            if file_indexes := self.contents.get('file_indexes'):
                rel_path = self._path
            else:
                rel_path = os.path.join(*path_list)
            raise ValueError(f'file not exists in "{rel_path}".\n [{", ".join(files)}]')

        if file_indexes := self.contents.get('file_indexes'):
            with zipfile.ZipFile(rootpath) as zf:
                idx = file_indexes[files.index(key)]
                return zf.open(zf.namelist()[idx])
        else:
            path_list.insert(0, rootpath)
            path = os.path.join(*path_list)
            return open(path, 'rb')

    def _open_as_string(self, key):
        """Opens a file as binary, decodes it as UTF-8, and splits it into lines.

        Args:
            key: The key to identify the file.

        Returns:
            list: The lines of the file as strings.
        """
        with self._open_as_fileobject(key) as f:
            string  = f.read().decode('UTF-8').split('\n')
        return string

    def __getitem__(self, key):
        """Returns the value associated with the given key.

        Args:
            key: The key to retrieve the value.

        Returns:
            object: The value associated with the key.

        Raises:
            KeyError: If the key is not found.
        """
        return self.__getattr__(key)
        
    def __getattr__(self, key):
        """
        Get attribute by name.

        Args:
            key (str): The name of the attribute to retrieve.

        Returns:
            Parameter or file object: The parameter object if the key is found in parameter files, otherwise the file object.

        Examples:
            obj = Dataset()
            param = obj.some_key  # Returns a Parameter object or file object.
        """
        key = key[1:] if key.startswith('_') else key #new code
        
        if file := [f for f in self.contents['files'] if (f == key or f.replace('.', '_') == key)]:
            fileobj = self._open_as_fileobject(file.pop())
            if self._is_binary(fileobj):
                return fileobj
            par = Parameter(fileobj.read().decode('UTF-8').split('\n'), 
                            name=key, scan_id=self._scan_id, reco_id=self._reco_id)
            return par if par.header else fileobj.read().decode('UTF-8').split('\n')
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")

    @property
    def contents(self):
        return self._contents

    @staticmethod
    def _is_binary(fileobj, bytes=512):
        block = fileobj.read(bytes)
        fileobj.seek(0)
        return b'\x00' in block


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
    def __init__(self, path, debug=False):
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
    def _check_dataset_validity(self, path):
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
        self._path = os.path.abspath(path)
        if not os.path.exists(self._path):
            raise FileNotFoundError(f"The path '{self._path}' does not exist.")
        if os.path.isdir(self._path):
            self._contents = self._fetch_dir(self._path)
            self.is_compressed = False
        elif os.path.isfile(self._path) and zipfile.is_zipfile(self._path):
            self._contents = self._fetch_zip(self._path)
            self.is_compressed = True
        else:
            raise ValueError(f"The path '{self._path}' does not meet the required criteria.")
    
    def _construct(self):    # sourcery skip: low-code-quality
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
