"""Base functionality for handling buffer and method operations in pvobj.

This module defines core classes that offer foundational utilities for managing and processing raw datasets.
The classes provide methods for handling file operations, such as opening and closing file buffers, fetching 
directory structures, and more, all while using an object-oriented approach to maintain and access these datasets.

Classes:
    BaseBufferHandler: Manages file buffer operations, ensuring proper opening, closing, and context management of file streams.
    BaseMethods: Extends BaseBufferHandler to include various file and directory handling methods necessary 
    for accessing and managing dataset contents.
"""

from __future__ import annotations
import os
from zipfile import ZipFile
from collections import OrderedDict, defaultdict
from pathlib import Path
from .parameters import Parameter
from xnippy.formatter import PathFormatter
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, List
    from .types import PvFileBuffer


class BaseBufferHandler(PathFormatter):
    """Handles buffer management for file operations, ensuring all file streams are properly managed.

    This class provides context management for file buffers, allowing for easy and safe opening and closing 
    of file streams. It ensures that all buffers are closed when no longer needed, preventing resource leakage.

    Attributes:
        _buffers (Union[List[BufferedReader], List[ZipExtFile]]): A list of file buffer objects.
    """
    _buffers: List[PvFileBuffer] = []
    def close(self):
        """Closes all open file buffers managed by this handler."""
        if self._buffers:
            for b in self._buffers:
                if not b.closed:
                    b.close()
    
    def __enter__(self):
        """Enters the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the runtime context and closes the file buffers, handling any exceptions."""
        self.close()
        return False


class BaseMethods(BaseBufferHandler):
    """Provides utility methods for handling files and directories within PvObjects.

    This class offers methods to fetch directory structures, handle zip file contents, and open files either 
    as file objects or as readable strings. It also provides a property to access the contents of directories 
    and zip files, tailored to the needs of managing Bruker raw datasets.

    Attributes:
        _scan_id (Optional[int]): The identifier for a specific scan, used in file path resolutions.
        _reco_id (Optional[int]): The identifier for a specific reconstruction, used in file path resolutions.
        _path (Optional[Path]): The base path for file operations.
        _rootpath (Optional[Path]): The root path of the dataset, used for resolving relative paths.
        _contents (Optional[dict]): A structured dictionary containing directory and file details.
    """
    _scan_id: int = None
    _reco_id: int = None
    _path: 'Path' = None
    _rootpath: 'Path' = None
    _contents: 'Path' = None
    
    def isinstance(self, name: str):
        """Check if the class name matches the provided string.

        This method compares the class name of the current instance with a given string to determine if they match.

        Args:
            name (str): The class name to check against the instance's class name.

        Returns:
            bool: True if the given name matches the instance's class name, otherwise False.
        """
        return self.__class__.__name__ == name
    
    @staticmethod
    def _fetch_dir(path: 'Path'):
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
        abspath = path.absolute()
        for dirpath, dirnames, filenames in os.walk(abspath):
            normalized_dirpath = os.path.normpath(dirpath)
            relative_path = os.path.relpath(normalized_dirpath, abspath)
            file_sizes = [os.path.getsize(os.path.join(dirpath, f)) for f in filenames]
            contents[relative_path] = {'dirs': dirnames, 'files': filenames, 
                                       'file_indexes': [], 'file_sizes': file_sizes}
        return contents
    
    @staticmethod
    def _fetch_zip(path: 'Path'):
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
        with ZipFile(path) as zip_file:
            contents = defaultdict(lambda: {'dirs': set(), 'files': [], 'file_indexes': [], 'file_sizes': []})
            for i, item in enumerate(zip_file.infolist()):
                if not item.is_dir():
                    dirpath, filename = os.path.split(item.filename)
                    contents[dirpath]['files'].append(filename)
                    contents[dirpath]['file_indexes'].append(i)
                    contents[dirpath]['file_sizes'].append(item.file_size)
                    while dirpath:
                        dirpath, dirname = os.path.split(dirpath)
                        if dirname:
                            contents[dirpath]['dirs'].add(dirname)
        return contents
    
    def _open_as_fileobject(self, key: str):
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
            with ZipFile(rootpath) as zf:
                idx = file_indexes[files.index(key)]
                return zf.open(zf.namelist()[idx])
        else:
            path_list.insert(0, rootpath)
            path = os.path.join(*path_list)
            return open(path, 'rb')

    def _open_as_string(self, key: str):
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
        
    def __getattr__(self, key: str):
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
            string_list = fileobj.read().decode('UTF-8').split('\n')
            fileobj.close()
            par = Parameter(string_list, 
                            name=key, scan_id=self._scan_id, reco_id=self._reco_id)
            return par if par.is_parameter() else string_list
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")

    @property
    def contents(self):
        """Access the contents dictionary holding directory and file details.

        This property provides access to a structured dictionary that organizes directory and file information,
        facilitating file operations across the class methods.

        Returns:
            dict: The contents dictionary with details about directories and files.
        """
        return self._contents

    def get_fid(self, scan_id:Optional[int] = None):
        """Retrieve the file object for the 'fid' or 'rawdata.job0' file from the dataset.

        This method attempts to fetch the 'fid' file commonly used in imaging datasets. If 'fid' is not found,
        it tries 'rawdata.job0'. It uses internal methods to navigate through dataset structures based on provided scan ID.

        Args:
            scan_id (Optional[int]): The identifier for the scan. Necessary if the class structure requires it to fetch data.

        Returns:
            BufferedReader: The file object for the 'fid' or 'rawdata.job0'.

        Raises:
            TypeError: If 'scan_id' is required but not provided.
            FileNotFoundError: If neither 'fid' nor 'rawdata.job0' files are found in the dataset.
        """
        try:
            pvobj = self.get_scan(scan_id) if hasattr(self, 'get_scan') else self
        except KeyError:
            raise TypeError("Missing required argument: 'scan_id must be provided for {self.__class__.__name__}.")
        fid_files = ['fid', 'rawdata.job0']
        for fid in fid_files:
            if fid in pvobj.contents['files']:
                return getattr(pvobj, fid)
        raise FileNotFoundError(f"The required file '{' or '.join(fid_files)}' does not exist. "
                                "Please check the dataset and ensure the file is in the expected location.")
    
    def get_2dseq(self, scan_id:Optional[int] = None, reco_id:Optional[int] = None):
        """Retrieve the '2dseq' file from the dataset for a specific scan and reconstruction.

        This method navigates through the dataset structure to fetch the '2dseq' file, a common data file in imaging datasets.

        Args:
            scan_id (Optional[int]): The scan ID to navigate to the correct scan. Required if the dataset structure is hierarchical.
            reco_id (Optional[int]): The reconstruction ID. Required if multiple reconstructions exist and are not specified.

        Returns:
            BufferedReader: The file object for the '2dseq'.

        Raises:
            TypeError: If necessary IDs are not provided.
            FileNotFoundError: If the '2dseq' file is not found in the dataset.
        """
        try:
            if scan_id and hasattr(self, 'get_scan'):
                pvobj = self.get_scan(scan_id).get_reco(reco_id)
            elif hasattr(self, 'get_reco'):
                reco_id = reco_id or sorted(self.avail).pop(0)
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
    def _is_binary(fileobj: PvFileBuffer, bytes: int = 512):
        """Determine if a file is binary by reading a block of data.

        Args:
            fileobj (BufferedReader): The file object to check.
            bytes (int): Number of bytes to read for the check.

        Returns:
            bool: True if the file contains binary data, otherwise False.
        """
        block = fileobj.read(bytes)
        fileobj.seek(0)
        return b'\x00' in block