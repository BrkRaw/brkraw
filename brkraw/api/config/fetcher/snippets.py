"""Provides functionality to manage and synchronize snippets across local and remote sources.

This module defines a `Snippets` class which aggregates snippets from various sources,
handles their synchronization, and ensures that the snippets are up-to-date according to
user-specified modes (plugin, preset, bids, app). It supports operations on snippets
fetched from both local file systems and remote repositories, offering features to check
connectivity, fetch content, and validate snippet integrity.

Classes:
    Snippets: Manages the aggregation and synchronization of snippets based on specified modes.
"""

from __future__ import annotations
import os
import warnings
from pathlib import Path
from .base import Fetcher
from brkraw.api.config.snippet import PlugInSnippet
from brkraw.api.config.snippet import BIDSSnippet
from brkraw.api.config.snippet import PresetSnippet
from brkraw.api.config.snippet import AppSnippet
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import List
    from typing import Tuple, Optional, Literal
    from brkraw.api.config.snippet.base import Snippet


class Snippets(Fetcher):
    """Manages the aggregation of snippets from various sources based on the specified mode.

    This class integrates local and remote snippet sources, handling their fetching, storing,
    and updating based on connectivity and cache settings.
    """
    path: Optional[Path]
    mode: Literal['plugin', 'preset', 'bids', 'app']
    is_cache: bool
    _fetched: bool = False
    _template: List[Snippet] = []
    _remote_snippets: List[Snippet] = []
    _local_snippets: List = [Snippet]
    _template_snippets: List = [Snippet]
    
    def __init__(self, 
                 repos: dict,
                 mode: Literal['plugin', 'preset', 'bids', 'app'],
                 path: Tuple[Optional['Path'], 'bool'] = (None, False)
                 ) -> None:
        """Initializes the Snippets object with specified repository configurations and operational mode.

        Args:
            repos (dict): A dictionary containing repository configurations.
            mode (Literal['plugin', 'preset', 'bids', 'app']): The operational mode determining the type of snippets to manage.
            path (Tuple[Optional[Path], bool], optional): A tuple containing the path to local storage and a boolean indicating cache usage.
        """
        self.repos = repos
        self.mode = mode
        self.path = self._resolve(path[0])
        self.is_cache = path[1]
        self._set_auth()
        self._fetch_local_contents()
        self._template = [c[mode]['template'] for c in repos if 'template' in c[mode]]
        
    def _fetch_local_contents(self) -> Optional[list]:
        """Fetches snippets from local storage based on the current mode and path settings.

        Gathers contents from the specified directory and converts them into snippets. This operation
        is skipped if caching is enabled.

        Returns:
            Optional[list]: Returns None if caching is enabled, otherwise returns a list of fetched local contents.
        """
        if self.is_cache:
            return None
        if self.mode in ['plugin', 'preset', 'bids']:
            contents = []
            for path, dirs, files in os.walk(self.path):
                child = {'path':self._resolve(path), 
                         'dirs':{d:self._resolve(path) / d for d in dirs}, 
                         'files':{f:self._resolve(path) / f for f in files}}
                contents.append(child)
            self._convert_contents_to_snippets([contents], remote=False)
            
    def _fetch_remote_contents(self) -> None:
        """Fetches snippets from remote repositories if connected and not previously fetched.

        Retrieves snippet data from remote sources as specified by the repository configuration
        and converts them into snippet objects. Updates the fetched status upon completion.
        """
        if self.repos and self.mode in ['plugin', 'preset', 'bids']:
            contents = [self._walk_github_repo(repo_url=repo['url'],
                                               path=repo[self.mode]['path'],
                                               auth=self._auth[i]) for i, repo in enumerate(self.repos)]
            self._convert_contents_to_snippets(contents=contents, remote=True)
            self._fetched = True        
            
    def _convert_contents_to_snippets(self, contents: list, remote: bool = False) -> None:
        """Converts fetched contents from either local or remote sources into snippet objects.

        Iterates over fetched contents, creating snippet objects which are then stored appropriately
        based on their validation status and whether they match predefined templates.

        Args:
            contents (list): List of contents fetched from either local or remote sources.
            remote (bool, optional): Flag indicating whether the contents are from remote sources.
        """
        for repo_id, contents in enumerate(contents):
            for c in contents:
                if remote:
                    snippet = self._snippet(contents=c, auth=self._auth[repo_id], remote=remote)
                    self._store_remote_snippet(repo_id=repo_id, snippet=snippet)
                else:
                    snippet = self._snippet(contents=c, remote=remote)
                    if snippet.is_valid and \
                        snippet.name not in [s.name for s in self._local_snippets]:
                        self._local_snippets.append(snippet)
                        
    def _store_remote_snippet(self, repo_id: int, snippet: Snippet):
        """Stores validated remote snippets into the appropriate lists based on template matching.

        Checks if the snippet is valid and if it matches a template or not. Based on this,
        the snippet is added to the respective list (template snippets or general remote snippets).

        Args:
            repo_id (int): The repository ID corresponding to the snippet source.
            snippet (Snippet): The snippet object to be stored.
        """
        if not snippet.is_valid:
            return None
        if self._is_template(repo_id, snippet) and \
            snippet.name not in [s.name for s in self._template_snippets]:
            self._template_snippets.append(snippet)
        elif not self._is_template(repo_id, snippet) and \
            snippet.name not in [s.name for s in self._remote_snippets]:
            self._remote_snippets.append(snippet)
            
    @property
    def _snippet(self):
        """Determines the snippet class based on the operational mode.

        Returns:
            Type[Snippet]: Returns the class type corresponding to the operational mode (Plugin, Preset, BIDS, App).
        """
        if self.mode == 'plugin':
            return PlugInSnippet
        elif self.mode == 'preset':
            return PresetSnippet
        elif self.mode == 'bids':
            return BIDSSnippet
        else:
            return AppSnippet
    
    @property
    def remote(self):
        """Access the remote snippets if available. Fetches the snippets from a remote source if not already fetched
        and if a network connection is available.

        Returns:
            Any: The remote snippets if available and connected, otherwise None.

        Raises:
            Warning: If the connection to fetch remote snippets fails.
        """
        if self._remote_snippets:
            return self._remote_snippets
        else:
            if self.is_connected():
                self._fetch_remote_contents()
                return self._remote_snippets
            else:
                warnings.warn("Connection failed. Please check your network settings.")
                return None
    
    def _is_template(self, repo_id: int, snippet: Snippet) -> bool:
        """Test given snippet is template. This internal method used to exclude template snippets from avail."""
        return any(snippet.name == t for t in self._template[repo_id])
    
    @property
    def local(self):
        return self._local_snippets

    @property
    def is_up_to_date(self):
        return self._fetched