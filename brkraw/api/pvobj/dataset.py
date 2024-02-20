import os
import re
import zipfile
from collections import OrderedDict
try:
    from .parser import Parameter
except ImportError:
    # case for debugging
    from brkraw.api.pvobj.parser import Parameter

class BaseMethods:
    _scan_id = None
    _reco_id = None
    _path = None
    _rootpath = None
    _contents = None
    _parameter_files = None
    _binary_files = None
    
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
            all_paths = {os.path.dirname(item.filename) for item in zip_file.infolist() if item.is_dir()}
            contents = OrderedDict({path: {'dirs': set(), 'files': [], 'file_indexes': []} for path in all_paths})
            for i, item in enumerate(zip_file.infolist()):
                if not item.is_dir():
                    dirpath, filename = os.path.split(item.filename)
                    contents[dirpath]['files'].append(filename)
                    contents[dirpath]['file_indexes'].append(i)
                    # Add missing parent directories
                    parent_path = dirpath
                    while parent_path != '':
                        parent_path = os.path.dirname(parent_path)
                        if parent_path not in contents:
                            contents[parent_path] = {'dirs': set(), 'files': [], 'file_indexes': []}
            for sub_path in all_paths:
                parent_path, dirname = os.path.split(sub_path.rstrip('/'))
                if parent_path in contents:
                    contents[parent_path]['dirs'].add(dirname)
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
        contents = self._contents if 'files' in self._contents else self._contents[list(self._contents.keys())[0]]
        rootpath = self._rootpath if 'files' in self._contents else self._path
        files = contents.get('files')

        if key not in files:
            raise ValueError(f'file not exists. [{",".join(files)}]')

        if file_indexes := contents.get('file_indexes'):
            with zipfile.ZipFile(rootpath) as zf:
                idx = file_indexes[files.index(key)]
                return zf.open(zf.namelist()[idx])
        else:
            path_list = [rootpath, *(str(self._scan_id) if self._scan_id else []), *(['pdata', str(self._reco_id)] if self._reco_id else []), key]
            path = os.path.join(*path_list)
            return open(path, 'rb')

    def _open_as_binary(self, key):
        """Opens a file as binary and reads its contents.

        Args:
            key: The key to identify the file.

        Returns:
            bytes: The binary contents of the file.
        """
        return self._open_as_fileobject(key).read()

    def _open_as_string(self, key):
        """Opens a file as binary, decodes it as UTF-8, and splits it into lines.

        Args:
            key: The key to identify the file.

        Returns:
            list: The lines of the file as strings.
        """
        return self._open_as_binary(key).decode('UTF-8').split('\n')

    def __getitem__(self, key):
        """Returns the value associated with the given key.

        Args:
            key: The key to retrieve the value.

        Returns:
            object: The value associated with the key.

        Raises:
            KeyError: If the key is not found.
        """
        if key in self._parameter_files:
            return Parameter(self._open_as_string(key), name=key, scan_id=self._scan_id, reco_id=self._reco_id)
        elif key in self._binary_files:
            return self._open_as_binary(key)
        else:
            return self._open_as_fileobject(key)


class PvDataset(BaseMethods):
    def __init__(self, path):
        self._check_dataset_validity(path)
        self._construct()
        if root_content := [c for c in self._contents.values() if 'subject' in c['files']]:
            setattr(self, 'subject', root_content)
    
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
    
    def _construct(self):
        """
        Constructs the object by organizing the contents.

        This method constructs the object by organizing the contents based on the provided directory structure.
        It iterates over the sorted contents and updates the `_scans` and `_backup` dictionaries accordingly.
        After processing, it removes the processed paths from the `_contents` dictionary.

        Returns:
            None
        """
        self._scans = OrderedDict()
        self._backup = OrderedDict()
        to_remove = []
        for path, contents in sorted(self._contents.items()):
            if not path:
                self._root = contents
                to_remove.append(path)
            else:
                if matched := re.match(r'(?:.*/)?(\d+)/pdata/(\d+)$', path) or re.match(
                    r'(?:.*/)?(\d+)$', path
                ):  
                    scan_id = int(matched.group(1))
                    if scan_id not in self._scans:
                        self._scans[scan_id] = PvScan(scan_id, (self.path, path))
                    if 'pdata' in contents['dirs']:
                        self._scans[scan_id].update(contents)
                    elif len(matched.groups()) == 2:
                        reco_id = int(matched.group(2))
                        self._scans[scan_id].set_reco(path, reco_id, contents)
                    
                    to_remove.append(path)
                if not contents['files']:
                    to_remove.append(path)
                elif 'subject' not in contents['files'] and path not in to_remove:
                    self._backup[path] = contents
                    to_remove.append(path)
            
        for path in to_remove:
            del self._contents[path]

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
        return list(self._scans)
    
    def get_scan(self, scan_id):
        return self._scans[scan_id]
    
    def get_reco(self, scan_id, reco_id):
        return self.get_scan(scan_id).get_reco(reco_id)
    
    def __dir__(self):
        return ['path', 'avail', 'get_scan', 'get_reco']
    


class PvScan(BaseMethods):
    def __init__(self, scan_id, pathes, contents=None, recos=None):
        self._scan_id = scan_id
        self._rootpath, self._path = pathes
        self.update(contents)
        self._recos = OrderedDict(recos) if recos else OrderedDict()
    
    def update(self, contents):
        self._contents = contents
    
    def set_reco(self, path, reco_id, contents):
        self._recos[reco_id] = PvReco(self._scan_id, reco_id, (self._rootpath, path), contents)
    
    def get_reco(self, reco_id):
        return self._recos[reco_id]
    
    @property
    def path(self):
        return self._path
    
    @property
    def avail(self):
        return list(self._recos)
    
    def __dir__(self):
        return ['path', 'avail', 'get_reco']
    
    
class PvReco(BaseMethods):
    def __init__(self, scan_id, reco_id, pathes, contents):
        self._scan_id = scan_id
        self._reco_id = reco_id
        self._rootpath, self._path = pathes
        self._contents = contents
        
    @property
    def path(self):
        return self._path
        
    def __dir__(self):
        return ['path']