"""This module implements a ModuleLoader class that allows importing Python modules from either 
a bytes object or a file path.

It is designed to be used within PlugIn Snippets to dynamically load modules without requiring them to be 
pre-installed or located in a standard file system path.
"""

from __future__ import annotations
import sys
import importlib
from importlib.machinery import ModuleSpec
from importlib.abc import SourceLoader
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Union, Optional


class ModuleLoader(SourceLoader):
    """A custom loader that imports a Python module from a bytes object or from a filepath.

    This loader supports dynamic execution of Python code, which can be especially useful in environments
    where plugins or modules need to be loaded from non-standard locations or directly from memory.

    Attributes:
        data (bytes, optional): The bytes object containing the source code of the module.
        filepath (Path, optional): The file path to the module if it's not loaded from bytes.
    """
    def __init__(self, module: Union[Path, bytes]):
        """Initializes the ModuleLoader with either a path to the module or its bytes content.

        Args:
            module (Union[Path, bytes]): The source of the module, either as a path or bytes.
        """
        if isinstance(module, bytes):
            self.data, self.filepath = module, None
        else:
            self.data, self.filepath = None, module

    def get_data(self, path: Optional[Path]):
        """Fetches the module's data from bytes or a file.

        Args:
            path (Path, optional): The path from which to load the module data if it's not already provided as bytes.

        Returns:
            bytes: The raw data of the module.
        """
        if self.data:
            return self.data
        elif path and Path(path).is_file():
            with open(path, 'rb') as file:
                return file.read()
        else:
            raise FileNotFoundError(f"No such file: {path}")

    def get_filename(self, fullname: Optional[str] = None):
        """Retrieves the filename of the module being loaded.

        Args:
            fullname (str, optional): The full name of the module.

        Returns:
            str: The filepath if it's defined, otherwise a dummy string for byte-loaded modules.
        """
        return str(self.filepath) if self.filepath else "<byte-loaded>"
        
    def get_module(self, name: str) -> ModuleSpec:
        """Creates and returns a module object from the provided data.

        This method constructs a module using the spec provided by this loader.

        Args:
            name (str): The name of the module.

        Returns:
            ModuleSpec: The module object loaded and ready for use.
        """
        spec = ModuleSpec(name=name, loader=self, origin=self.get_filename())
        module = importlib.util.module_from_spec(spec)
        self.exec_module(module)
        sys.modules[name] = module
        return module
    