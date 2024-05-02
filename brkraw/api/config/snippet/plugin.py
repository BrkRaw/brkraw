"""Provides a PlugInSnippet class that allows for plugin source code or code loaded in memory
to be imported as a Python module. This extends the functionality of the brkraw module at the
application level.

This class facilitates the quick testing of code without the need for environment setup for plugin downloads.

Changes:
    2024.5.1: Initial design and implementation of the PlugIn Snippet architecture. Initially tested for the tonifti app.
    TODO: The PlugIn module will be a standard method to extend functionality across the entire apps.

Author: Sung-Ho Lee (shlee@unc.edu)
"""

from __future__ import annotations
import sys
import re
import yaml
import warnings
import subprocess as subproc
from pathlib import Path
from tqdm import tqdm
from .base import Snippet
from .loader import ModuleLoader
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Tuple, Dict, Optional, Union
    

class PlugIn(Snippet):
    """Handles the inspection and management of plugins, either locally or from remote sources.
    
    This class supports dynamic loading of plugins into memory for immediate use without the need for disk storage,
    facilitating rapid development and testing of plugin functionalities.
    """
    _remote: bool
    _module_loaded: bool
    _dependencies_tested: bool = False 
    _auth: Tuple[str, str]
    _data: Dict = {}
    _contents: Dict
    
    def __init__(self, 
                 contents: dict, 
                 auth: Optional[Tuple[str, str]] = None, 
                 remote: bool = False):
        """Initializes the plugin with specified contents, authentication for remote access, and remote status.

        Args:
            contents (dict): Contains keys of path, dirs, and files, similar to os.walk but structured as a dictionary.
                             Each directory and file is also mapped as a key (filename) to a value (path or download_url).
            auth (Tuple[str, str], optional): Credentials for using the GitHub API if needed.
            remote (bool): True if the plugin is loaded remotely, False otherwise.
        """
        self._auth = auth
        self._contents = contents
        self._remote = remote
        self._content_parser()

    def set(self, skip_dependency_check: bool = False, *args, **kwargs):
        """Sets the plugin's parameters and ensures dependencies are resolved and the module is loaded.

        This method acts as a setup routine by testing dependencies, downloading necessary files,
        and dynamically importing the module and call module with given input arguments.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            The result of calling the imported module with provided arguments.
        """
        if not self._module_loaded:
            self.download()
        if not self._dependencies_tested and not skip_dependency_check:
            self.resolve_dependencies()
        return self._imported_module(*args, **kwargs)
    
    def resolve_dependencies(self):
        """Checks and installs any missing dependencies specified in the plugin's manifest file."""
        ptrn = r'(\w+)\s*(>=|<=|==|!=|>|<)\s*([0-9]+(?:\.[0-9]+)*)?'
        deps = self._manifest['dependencies']
        print(f"++ Resolving python module dependencies...\n  -> {deps}")
        for module in tqdm(deps, desc=' -Dependencies', ncols=80):
            if matched := re.match(ptrn, module):
                self._status = None
                self._pip_install(matched)
        self._dependencies_tested = True
    
    def _pip_install(self, matched):
        """Executes the pip install command for the matched dependency.

        Args:
            matched (re.Match): A match object containing the module and version information.

        This method handles the pip installation process, directing output and errors appropriately.
        """
        m, r, v = matched.groups()
        cmd = [sys.executable, "-m", "pip", "install", f"{m}{r or ''}{v or ''}"]
        displayed = 0
        with subproc.Popen(cmd, stdout=subproc.PIPE, stderr=subproc.PIPE, 
                           text=True, bufsize=1, universal_newlines=True) as proc:
            for l in proc.stdout:
                if 'satisfied' in l.lower():
                    if not displayed:
                        print(f" + Required already satisfied: {m}")
                    displayed += 1
                elif 'collecting' in l.lower():
                    if not displayed:
                        print(f" + Installing '{m}' to resolve dependencies.")
                    displayed += 1
            proc.wait()
            if proc.returncode != 0:
                warnings.warn(f"'Errors during resolving dependencies': {''.join(proc.stderr)}")
        
    def download(self, dest: Optional[Path] = None, force: bool = False):
        """Downloads the plugin to a specified destination or loads it directly into memory if no destination is provided.
        This method also checks if the file already exists at the destination and optionally overwrites it based on the 'force' parameter.

        Args:
            dest (Path, optional): The file system destination where the plugin files will be saved.
                                If None, files are loaded into memory.
            force (bool, optional): If True, existing files at the destination will be overwritten.
                                    Defaults to False.
        """
        if not self._remote:
            warnings.warn("Attempt to download failed: The plugin is already available "
                          "locally and cannot be downloaded again.", UserWarning)
            return False
        print(f"\n++ Downloading remote module to '{dest or 'memory'}'.")
        files = self._contents['files'] if dest else self._get_module_files()
        for filename, download_url in tqdm(files.items(), desc=' -Files', ncols=80):
            if dest:
                plugin_path = (dest / self.name)
                plugin_path.mkdir(exist_ok=True)
                plugin_file = plugin_path / filename
                if plugin_file.exists() and not force:
                    warnings.warn(f"Warning: File '{filename}' already exists. Skipping download. Use 'force=True' to overwrite.", 
                                  UserWarning)
                    continue  # Skip the download if file exists and force is False
                with open(plugin_file, 'wb') as f:
                    for chunk in self._download_buffer(download_url, auth=self._auth):
                        f.write(chunk)
            else:
                # When downloading to memory
                self._data[filename] = b''.join(self._download_buffer(download_url, auth=self._auth))
                self._module_loaded = True  # Mark the module as loaded


    def _get_module_files(self):
        return {f:url for f, url in self._contents['files'].items() if f.endswith('.py')} 

    def _content_parser(self):
        """Parses the contents of the plugin based on its current state (local or remote).

        This method sets the plugin's parameters and determines its validity based on the availability
        and correctness of the required data.
        """
        if len(self._contents['files']) == 0:
            self.is_valid = False
            return None
        self._parse_files()
        try:
            self._set_params()
        except KeyError:
            self.is_valid = False
            return None

    def _set_params(self):
        self.name = self._manifest['name']
        self.version = self._manifest['version']
        self.type = self._manifest['subtype']
        self.is_valid = True
        self._module_loaded = False if self._remote else True

    def _parse_files(self):
        """Processes the contents, loading the manifest if necessary."""
        for filename, file_loc in self._contents['files'].items():
            if filename.lower() == 'manifest.yaml':
                self._load_manifest(file_loc)

    def _parse_remote(self):
        """Processes the contents if the plugin is in a remote state, loading the manifest if necessary."""
        for filename, download_url in self._contents['files'].items():
            if filename.lower() == 'manifest.yaml':
                self._load_manifest(download_url)
    
    def _load_manifest(self, file_loc: Union[str, Path]):
        """Loads the plugin's manifest from a remote URL.

        Args:
            download_url (str): The URL from which to download the manifest.

        This method fetches and parses the plugin's manifest file, setting flags based on the contents.
        """
        if self._remote:
            bytes_data = b''.join(self._download_buffer(file_loc, auth=self._auth))
            self._manifest = yaml.safe_load(bytes_data)
        else:
            with open(file_loc, 'r') as f:
                self._manifest = yaml.safe_load(f)
        if self._manifest['type'] != 'plugin':
            warnings.warn(f"The type annotation for the '{self._manifest['name']}' plugin manifest is not set as 'plugin.' \
                    This may cause the plugin to function incorrectly.")
            self.is_valid = False
    
    @property
    def _imported_module(self):
        """Dynamically imports the module from loaded data.

        This method uses the information from the manifest to import the specified module and method dynamically.

        Returns:
            The imported method from the module.
        """
        source = self._manifest['source']
        f, c = source.split(':')
        mloc = self._data[f] if self._remote else self._contents['files'][f]
        loader = ModuleLoader(mloc)
        module = loader.get_module(self.name)
        return getattr(module, c)

    def __repr__(self):
        if self.is_valid:
            repr = f"PlugInSnippet<{self.type}>::{self.name}[{self.version}]"
            if self._remote:
                repr += '+InMemory' if self._module_loaded else '+Remote'
            return repr
        else:
            return "PlugInSnippet<?>::InValidPlugin"
