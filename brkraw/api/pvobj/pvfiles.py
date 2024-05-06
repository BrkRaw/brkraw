"""Provides the PvFiles class for managing individual files within a Paravision dataset.

This module includes the PvFiles class, derived from BaseMethods, specifically tailored to manage non-standard or loosely organized files within a dataset. It offers functionalities for dynamically handling arbitrary file inputs, making it versatile for datasets that do not conform to standard directory structures typically expected in Paravision studies.

Classes:
    PvFiles: Manages individual file access and operations, providing methods to handle arbitrary files efficiently and effectively. This class is especially useful for datasets that require flexible file management strategies.
"""

from __future__ import annotations
from .base import BaseMethods
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pathlib import Path

class PvFiles(BaseMethods):
    """Manages arbitrary files within a Paravision dataset, providing flexible file handling capabilities.

    This class extends BaseMethods to provide specialized handling of files that may not necessarily fit into
    a structured directory or standardized dataset format. It is particularly useful for datasets where files
    are spread across different locations or need to be accessed without a fixed directory structure.

    Attributes:
        _path (list): A list of resolved file paths that are currently managed by this instance.
        _contents (dict): A dictionary representing the contents currently available in this instance.
    """
    def __init__(self, *files: Path):
        """Initializes the PvFiles object with one or more files.

        Args:
            *files (Path): An arbitrary number of Path objects pointing to the files to be managed.
        """
        self.update(*files)
    
    def update(self, *files: Path):
        """Updates the managed files in the PvFiles instance.

        Args:
            *files (Path): An arbitrary number of Path objects pointing to the files to be managed.

        Notes:
            This method updates the list of file paths and the contents dictionary based on the files provided.
        """
        self
        self._path = [self._resolve(f) for f in files if self._resolve(f).exists()]
        self._contents = {"files": [f.name for f in self._path],
                          "dirs": [],
                          "file_indexes": []}        
    
    def _open_as_fileobject(self, key: str):
        """Opens a file as a file object based on the specified key.

        Args:
            key (str): The key or part of the file name to identify the file to open.

        Returns:
            file object: The opened file object corresponding to the key.

        Raises:
            KeyError: If the file corresponding to the key does not exist in the managed files.
        """
        if file_path := self._search_file_path(key):
            return open(file_path, 'rb')
        raise KeyError(f'Failed to find filename "{key}" from input files.\n [{self.contents.get("files")}]')
        
    def _search_file_path(self, key: str):
        """Searches for a file path that includes the specified key.

        Args:
            key (str): A substring of the file name to search for among the managed files.

        Returns:
            str or False: The full path of the file if found, False otherwise.
        """
        if files := [f for f in self._path if key in f]:
            return files.pop()
        else:
            return False
        
    def get_visu_pars(self, _:None=None):
        """A mock function to mimic getting 'visu_pars', typically used for testing or compatibility.

        Returns:
            str: The contents of 'visu_pars' if it exists, mimics behavior of similar functions in related classes.
        """
        return getattr(self, 'visu_pars')
        
    @property
    def path(self):
        """Returns the paths of the managed files.

        Returns:
            list: A list of file paths being managed by this instance.
        """
        return self._path
