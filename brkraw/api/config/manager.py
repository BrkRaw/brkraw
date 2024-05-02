"""Manager module for configuring, loading, or creating configuration files.

This module facilitates the management of configuration settings within the application, 
allowing configurations to be handled internally without file creation unless specifically 
requested by the user through CLI to create them in the home folder.
"""

from __future__ import annotations
import yaml
import warnings
from pathlib import Path
from .fetcher import SnippetsFetcher
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Tuple, Literal, Union, Optional


class Manager:
    """Manages the configuration settings for the application.

    This class ensures the existence of the configuration directory, loads or creates the configuration file,
    sets configuration values, and retrieves configuration values. It operates both globally and locally
    depending on the user's choice and the operational context.
    """
    config: dict = {}
    
    def __init__(self, tmpdir: Optional[Path] = None) -> None:
        """Initializes the configuration manager.

        This constructor sets up paths for the home directory, global and local configuration directories,
        and configuration file. It ensures the configuration directory exists and loads or creates the
        configuration based on its presence.

        Args:
            tmpdir (Optional[Path]): Temporary directory for storing configurations, defaults to the home directory.
        """
        self._home_dir = Path.home()
        self._default_dir = Path(__file__).absolute().parent
        self._local_dir = Path.cwd() / '.brkraw'
        self._global_dir = self._home_dir / '.brkraw'
        self._fname = 'config.yaml'
        self._tmpdir = tmpdir or self._home_dir / '.tmp'
        self.load()

    @property
    def created(self) -> Union[Literal['global', 'local'], list[str], bool]:
        """"Checks and returns the location where the configuration folder was created.

        Returns:
            Union[Literal['global', 'local'], list[str], bool]: Returns 'global' or 'local' if the config folder was created at that level,
            a list of locations if multiple exist, or False if no config folder is created.
        """
        created = [(f / self._fname).exists() for f in [self._global_dir, self._local_dir]]
        checked = [loc for i, loc in enumerate(['global', 'local']) if created[i]]
        checked = checked.pop() if len(checked) == 1 else checked
        return checked or False

    @property
    def config_dir(self) -> 'Path':
        """Determines and returns the appropriate configuration directory based on the existence and location of the config file.

        Returns:
            Path: Path to the configuration directory based on its existence and scope (global or local).
        """
        if isinstance(self.created, list):
            return self._local_dir
        elif isinstance(self.created, str):
            return self._local_dir if self.created == 'local' else self._global_dir
        return self._default_dir

    def load(self) -> None:
        """Loads an existing configuration file or creates a new one if it does not exist, filling the 'config' dictionary with settings."""
        with open(self.config_dir / self._fname) as f:
            self.config = yaml.safe_load(f)
    
    def create(self, target: Literal['local', 'global'] = 'local', 
               force: bool = False) -> bool:
        """Creates a configuration file at the specified location.

        Args:
            target (Literal['local', 'global']): Target directory for creating the configuration file, defaults to 'local'.
            force (bool): If True, overwrites the existing configuration file, defaults to False.

        Returns:
            bool: True if the file was created successfully, False otherwise.
        """
        if not self.config:
            self.load()
        config_dir = self._local_dir if target == 'local' else self._global_dir
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / self._fname
        if config_file.exists():
            if not force:
                warnings.warn("Config file exists, please use 'force' option if you want overwrite.",
                              UserWarning)
                return False
        with open(config_dir / self._fname, 'w') as f:
            yaml.safe_dump(self.config, f, sort_keys=False)

    def get_fetcher(self, mode: Literal['plugin', 'preset', 'bids', 'app']) -> SnippetsFetcher:
        """Returns the appropriate fetcher based on the mode.

        Args:
            mode (Literal['plugin', 'preset', 'bids', 'app']): The mode determining which type of fetcher to return.

        Returns:
            SnippetsFetcher: An instance of SnippetsFetcher configured for the specified mode.
        """
        if mode in ['plugin', 'preset', 'bids']:
            return self._get_snippet_fetcher(mode)
        else:
            return self._get_app_fetcher()

    def _get_snippet_fetcher(self, mode: Literal['plugin', 'preset', 'bids']) -> 'SnippetsFetcher':
        """Retrieves a configured SnippetsFetcher for the specified mode to handle fetching of snippets.

        Args:
            mode (Literal['plugin', 'preset', 'bids']): The specific category of snippets to fetch.

        Returns:
            SnippetsFetcher: A fetcher configured for fetching snippets of the specified type.
        """
        return SnippetsFetcher(repos=self.config['snippets']['repo'],
                               mode=mode,
                               path=self._check_dir(mode))

    def _get_app_fetcher(self) -> 'SnippetsFetcher':
        """Retrieves a SnippetsFetcher for application handling.

        Returns:
            SnippetsFetcher: A fetcher configured to handle application-specific tasks.
        """
        return SnippetsFetcher(repos=self.config['app'],
                               mode='app')
    
    def _check_dir(self, type_: Literal['plugin', 'preset', 'bids']) -> Tuple['Path', bool]:
        """Checks and prepares the directory for the specified snippet type, ensuring it exists.

        Args:
            type_ (Literal['plugin', 'preset', 'bids']): The type of snippet for which the directory is checked.

        Returns:
            Tuple[Path, bool]: A tuple containing the path to the directory and a cache flag indicating
                                if caching is necessary (True if so).
        """
        path, cache = (self.config_dir / type_, False) if self.created else (self._tmpdir, True)
        if not path.exists():
            path.mkdir()
        return path, cache