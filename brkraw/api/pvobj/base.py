import os
import zipfile
from collections import OrderedDict
from collections import defaultdict
from .parameters import Parameter

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
            KeyError: If the key does not exist in the files.
        """
        rootpath = self._rootpath or self._path
        if not self.contents:
            raise KeyError(f'Failed to load contents list from "{rootpath}".')
        files = self.contents.get('files')
        path_list = [*([str(self._scan_id)] if self._scan_id else []), *(['pdata', str(self._reco_id)] if self._reco_id else []), key]

        if key not in files:
            if file_indexes := self.contents.get('file_indexes'):
                rel_path = self._path
            else:
                rel_path = os.path.join(*path_list)
            raise KeyError(f'Failed to load filename "{key}" from folder "{rel_path}".\n [{", ".join(files)}]')

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
        key = key[1:] if key.startswith('_') else key 
        
        if file := [f for f in self.contents['files'] if (f == key or f.replace('.', '_') == key)]:
            fileobj = self._open_as_fileobject(file.pop())
            if self._is_binary(fileobj):
                return fileobj
            par = Parameter(fileobj.read().decode('UTF-8').split('\n'), 
                            name=key, scan_id=self._scan_id, reco_id=self._reco_id)
            return par if par.is_parameter() else fileobj.read().decode('UTF-8').split('\n')
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")

    @property
    def contents(self):
        return self._contents

    def get_fid(self, scan_id:int|None = None):
        try:
            pvobj = self.get_scan(scan_id) if hasattr(self, 'get_scan') else self
        except KeyError:
            raise TypeError("Missing required argument: 'scan_id must be provided for {self.__class__.__name__}.")
        fid_files = ['fid', 'rawdata.job0']
        for fid in ['fid', 'rawdata.job0']:
            if fid in pvobj.contents['files']:
                return getattr(pvobj, fid)
        raise FileNotFoundError(f"The required file '{' or '.join(fid_files)}' does not exist. "
                                "Please check the dataset and ensure the file is in the expected location.")
    
    def get_2dseq(self, scan_id:int|None = None, reco_id:int|None = None):
        try:
            if scan_id and hasattr(self, 'get_scan'):
                pvobj = self.get_scan(scan_id).get_reco(reco_id)
            elif reco_id and hasattr(self, 'get_reco'):
                pvobj = self.get_reco(reco_id)
            else:
                pvobj = self
        except KeyError:
            message = "Missing required argument: "
            if hasattr(self, 'get_scan'):
                message = f"{message} 'scan_id' and 'reco_id' "
            elif hasattr(self, 'get_reco'):
                message = f"{message} 'reco_id' "
            message = f"{message} must be provided for {self.__class__.__name__}."
            raise TypeError(message)
        try:
            return getattr(pvobj, '2dseq')
        except AttributeError:
            raise FileNotFoundError("The required file '2dseq' does not exist. "
                                    "Please check the dataset and ensure the file is in the expected location.")
        

    @staticmethod
    def _is_binary(fileobj, bytes=512):
        block = fileobj.read(bytes)
        fileobj.seek(0)
        return b'\x00' in block