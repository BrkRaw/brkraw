from __future__ import annotations
import re
import warnings
import requests
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import List, Tuple
    from typing import Optional, Union, Generator


class Fetcher:
    """Base Fetcher class 

    Returns:
        _type_: _description_

    Yields:
        _type_: _description_
    """
    _auth: Union[List[Tuple[str, str]], Tuple[str, str]]
    repos: dict
    
    @staticmethod
    def is_connected():
        try:
            Fetcher._fetch_from_url('https://api.github.com')
        except (requests.ConnectTimeout, requests.ConnectionError, requests.RequestException):
            return False
        return True
    
    def _set_auth(self):
        """Set authentication to access repository"""
        if isinstance(self.repos, list):
            self._auth = [self._fetch_auth(repo) for repo in self.repos]
    
    @staticmethod
    def _fetch_auth(repo_dict: dict):
        if 'auth' in repo_dict:
            username = repo_dict['auth']['username']
            token = repo_dict['auth']['token']
            return (username, token) if username and token else None
        return None
    
    @staticmethod
    def _walk_github_repo(repo_url: dict, path: Optional['str'] = None, auth: Tuple[str, str] = None):
        """Recursively walk through directories in a GitHub repository."""
        base_url = Fetcher._decode_github_repo(repo_url=repo_url, path=path)
        return Fetcher._walk_dir(url=base_url, auth=auth)
    
    @staticmethod
    def _walk_dir(url, path='', auth: Tuple[str, str] = None):
        contents = Fetcher._fetch_from_url(url=url, auth=auth).json()
        dirs, files = Fetcher._fetch_directory_contents(contents)
        yield {'path':path, 
               'dirs':{d['name']:d['url'] for d in dirs}, 
               'files':{f['name']:f['download_url'] for f in files}}

        for dir in dirs:
            new_path = f"{path}/{dir['name']}" if path else dir['name']
            new_url = dir['url']
            yield from Fetcher._walk_dir(url=new_url, path=new_path, auth=auth)
    
    @staticmethod
    def _fetch_directory_contents(contents):
        dirs, files = [], []
        for i, item in enumerate(contents):
            if item['type'] == 'dir':
                dirs.append(item)
            elif item['type'] == 'file':
                files.append(item)
        return dirs, files
    
    @staticmethod
    def _decode_github_repo(repo_url: dict, path: Optional['str'] = None):
        ptrn_github = r'https://(?:[^/]+\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git])?'
        if matched := re.match(ptrn_github, repo_url):
            owner = matched['owner']
            repo = matched['repo']
            return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}" if path \
                else f"https://api.github.com/repos/{owner}/{repo}/contents"
    
    @staticmethod
    def _fetch_from_url(url: str, auth: Tuple[str, str] = None) -> Optional[requests.Response]:
        response = requests.get(url, auth=auth)
        if response.status_code == 200:
            return response
        else:
            warnings.warn(f"Failed to retrieve contents: {response.status_code}", UserWarning)
            return None

    @staticmethod
    def _download_buffer(url: dict,
                         chunk_size: int = 8192,
                         auth: Tuple[str, str] = None) -> Union[Generator, bool]:
        try:
            response = requests.get(url, stream=True, auth=auth)
            response.raise_for_status()
            return response.iter_content(chunk_size=chunk_size)
        except requests.RequestException as e:
            warnings.warn(f'Error downloading the file: {e}')
            return False
