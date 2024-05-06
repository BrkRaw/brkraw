from __future__ import annotations
from pathlib import Path
from .base import BaseMethods
from brkraw.api.data import Scan
from brkraw.api.pvobj import PvScan, PvReco, PvFiles
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Union


class ToNiftiPlugin(Scan, BaseMethods):
    """Base class for handling plugin operations, integrating scanning and basic method functionalities.

    This class initializes plugin operations with options for verbose output and integrates functionalities
    from the Scan and BaseMethods classes. It provides methods to close the plugin and clear any cached data.

    Args:
        pvobj (Union['PvScan', 'PvReco', 'PvFiles']): An object representing the PV (ParaVision) scan, reconstruction, 
                                                      or file data, which is central to initializing the plugin operations.
        verbose (bool): Flag to enable verbose output during operations, defaults to False.
        **kwargs: Additional keyword arguments that are passed to the superclass.

    Attributes:
        verbose (bool): Enables or disables verbose output.
    """
    def __init__(self, pvobj: Union['PvScan', 'PvReco', 'PvFiles'], 
                 verbose: bool=False, 
                 skip_dependency_check: bool=False,
                 **kwargs):
        """Initializes the BasePlugin with a PV object, optional verbosity, and other parameters.

        Args:
            pvobj (Union['PvScan', 'PvReco', 'PvFiles']): The primary object associated with ParaVision operations.
            verbose (bool, optional): If True, enables verbose output. Defaults to False.
            **kwargs: Arbitrary keyword arguments passed to the superclass initialization.
        """
        super().__init__(pvobj, **kwargs)
        self.verbose: bool = verbose
        self.skip_dependency_check: bool = skip_dependency_check
    
    def close(self):
        """Closes the plugin and clears any associated caches by invoking the clear_cache method.
        """
        super().close()
        self.clear_cache()
                
    def clear_cache(self):
        """Clears all cached data associated with the plugin. This involves deleting files that have been
        cached during plugin operations.
        """
        for buffer in self._buffers:
            file_path = Path(buffer.name)
            if file_path.exists():
                file_path.unlink()
