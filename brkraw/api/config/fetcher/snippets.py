"""Docstring."""

from __future__ import annotations
import os
from pathlib import Path
from .base import Fetcher
from brkraw.api.config.snippet import PlugInSnippet
from brkraw.api.config.snippet import BIDSSnippet
from brkraw.api.config.snippet import PresetSnippet
from brkraw.api.config.snippet import AppSnippet
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import List
    from typing import Tuple, Optional, Literal, Union
    from brkraw.api.config.snippet.base import Snippet


class Snippets(Fetcher):
    """Class aggregate all available plugins
    """
    path: Optional[Path]
    mode: Literal['plugin', 'preset', 'bids', 'app']
    is_cache: bool
    _template: List = []
    _remote_snippets: List = []
    _local_snippets: List = []
    _template_snippets: List = []
    
    def __init__(self, 
                 repos: dict,
                 mode: Literal['plugin', 'preset', 'bids', 'app'],
                 path: Tuple[Optional['Path'], 'bool'] = (None, False)
                 ) -> None:
        """_summary_

        Args:
            repos (dict): _description_
            path (Path, optional): _description_. Defaults to None.
            cache (bool, optional): _description_. Defaults to False.
        """
        self.repos = repos
        self.mode = mode
        self.path, self.is_cache = path
        self._set_auth()
        self._fetch_local_contents()
        self._template = [c[mode]['template'] for c in repos if 'template' in c[mode]]
        
    def _fetch_local_contents(self) -> Optional[list]:
        """
        """
        if self.is_cache:
            return None
        if self.mode in ['plugin', 'preset', 'bids']:
            contents = []
            for path, dirs, files in os.walk(self.path):
                child = {'path':path, 
                         'dirs':{d:Path(path) / d for d in dirs}, 
                         'files':{f:Path(path) / f for f in files}}
                contents.append(child)
            self._convert_contents_to_snippets([contents], remote=False)
            
    def _is_template(self, repo_id: int, snippet: Snippet) -> bool:
        return any(snippet.name == t for t in self._template[repo_id])
        
    def _fetch_remote_contents(self) -> None:
        """ built-in plugins from build-in dir
        """
        if self.repos and self.mode in ['plugin', 'preset', 'bids']:
            contents = [self._walk_github_repo(repo_url=repo['url'],
                                               path=repo[self.mode]['path'],
                                               auth=self._auth[i]) for i, repo in enumerate(self.repos)]
            self._convert_contents_to_snippets(contents=contents, remote=True)
            
    def _convert_contents_to_snippets(self, contents: list, remote: bool = False) -> None:
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
        return self._remote_snippets
    
    @property
    def local(self):
        return self._local_snippets
