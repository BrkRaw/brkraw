import os
from .base import BaseMethods

class PvFiles(BaseMethods):
    def __init__(self, *files):
        """_summary_

        Args:
            data_path (str): path of '2dseq' file in reco_dir
            pars_path (str): path of 'visu_pars' file in reco_dir
        """
        self.update(*files)
    
    def update(self, *files):
        self._path = [os.path.abspath(f) for f in files if os.path.exists(f)]
        self._contents = {"files": [os.path.basename(f) for f in self._path],
                          "dirs": [],
                          "file_indexes": []}        
    
    def _open_as_fileobject(self, key):
        """Override open_as_fileobject method

        Args:
            key: The key to identify the file.

        Returns:
            file object: The opened file object.

        Raises:
            ValueError: If the key does not exist in the files.
        """
        if file_path := self._search_file_path(key):
            return open(file_path, 'rb')
        raise KeyError(f'Failed to find filename "{key}" from input files.\n [{self.contents.get("files")}]')
        
    def _search_file_path(self, key):
        if files := [f for f in self._path if key in f]:
            return files.pop()
        else:
            return False
        
    def get_visu_pars(self, _:None=None):
        """ Mock function of PvScan """
        return getattr(self, 'visu_pars')
        
    @property
    def path(self):
        return self._path
