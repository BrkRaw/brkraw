"""Provides a base Fetcher class for accessing and manipulating content from remote repositories.

This module is designed to facilitate the retrieval of repository data, specifically from GitHub,
by providing methods to authenticate, fetch, and traverse directories. It integrates direct
API requests to handle repository contents and provides utility functions for downloading files
and walking through repository directories recursively.

Classes:
    Fetcher: A base class for fetching content from remote repositories with GitHub API integration.
"""

from __future__ import annotations
import re
import warnings
import requests
from brkraw.api.util.package import PathResolver
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, Union
    from typing import List, Tuple, Generator


class Fetcher(PathResolver):
    """Base class for fetching remote content with methods to authenticate and navigate repositories.

    The Fetcher class extends the functionality of PathResolver to include methods that handle
    the authentication and retrieval of data from remote GitHub repositories. It provides
    utilities to walk through repository directories, fetch file and directory contents,
    and download files as needed.

    Attributes:
        _auth (Union[List[Tuple[str, str]], Tuple[str, str]]): Authentication credentials for the repository.
        repos (dict): Configuration for the repositories to be accessed.
    """
    _auth: Union[List[Tuple[str, str]], Tuple[str, str]]
    repos: dict
    
    @staticmethod
    def is_connected():
        """Check if there is an internet connection available by pinging a known URL.

        Returns:
            bool: True if the connection is successful, False otherwise.
        """
        try:
            Fetcher._fetch_from_url('https://api.github.com')
        except (requests.ConnectTimeout, requests.ConnectionError, requests.RequestException):
            return False
        return True
    
    def _set_auth(self):
        """Set up authentication credentials for accessing configured repositories.

        Extracts and sets authentication details for each repository from the provided configurations.
        """
        if isinstance(self.repos, list):
            self._auth = [self._fetch_auth(repo) for repo in self.repos]
    
    @staticmethod
    def _fetch_auth(repo_dict: dict):
        """Fetch authentication credentials from a repository configuration.

        Args:
            repo_dict (dict): Repository configuration containing 'auth' fields.

        Returns:
            Optional[Tuple[str, str]]: A tuple containing username and token if both are present, otherwise None.
        """
        if 'auth' in repo_dict:
            username = repo_dict['auth']['username']
            token = repo_dict['auth']['token']
            return (username, token) if username and token else None
        return None
    
    @staticmethod
    def _walk_github_repo(repo_url: dict, path: Optional['str'] = None, auth: Tuple[str, str] = None):
        """Recursively walk through directories in a GitHub repository to fetch directory and file structure.

        Args:
            repo_url (dict): URL of the GitHub repository.
            path (Optional[str]): Specific path in the repository to start the walk.
            auth (Tuple[str, str]): Authentication credentials for accessing the repository.

        Yields:
            dict: A dictionary containing 'path', 'dirs', and 'files' with their respective URLs.
        """
        base_url = Fetcher._decode_github_repo(repo_url=repo_url, path=path)
        return Fetcher._walk_dir(url=base_url, auth=auth)
    
    @staticmethod
    def _walk_dir(url, path='', auth: Tuple[str, str] = None):
        """Walk through a specific directory in a repository.

        Args:
            url (str): URL of the directory to walk through.
            path (str): Path relative to the repository root.
            auth (Tuple[str, str]): Authentication credentials for accessing the repository.

        Yields:
            dict: A dictionary containing the path, directories, and files within the directory.
        """
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
        """Categorize contents of a directory into subdirectories and files.

        Args:
            contents (list): List of contents from a directory.

        Returns:
            tuple: A tuple containing lists of directories and files.
        """
        dirs, files = [], []
        for i, item in enumerate(contents):
            if item['type'] == 'dir':
                dirs.append(item)
            elif item['type'] == 'file':
                files.append(item)
        return dirs, files
    
    @staticmethod
    def _decode_github_repo(repo_url: dict, path: Optional['str'] = None):
        """Decode a GitHub repository URL to construct an API endpoint URL.

        Args:
            repo_url (dict): The GitHub repository URL.
            path (Optional[str]): An optional path within the repository.

        Returns:
            str: A constructed API endpoint URL based on the repository details.
        """
        ptrn_github = r'https://(?:[^/]+\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git])?'
        if matched := re.match(ptrn_github, repo_url):
            owner = matched['owner']
            repo = matched['repo']
            return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}" if path \
                else f"https://api.github.com/repos/{owner}/{repo}/contents"
    
    @staticmethod
    def _fetch_from_url(url: str, auth: Tuple[str, str] = None) -> Optional[requests.Response]:
        """Fetch data from a given URL using optional authentication.

        Args:
            url (str): The URL from which to fetch data.
            auth (Tuple[str, str]): Optional authentication credentials.

        Returns:
            Optional[requests.Response]: The response object if successful, otherwise None.
        """
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
        """Download file content from a URL in buffered chunks.

        Args:
            url (dict): The URL of the file to download.
            chunk_size (int): The size of each chunk in bytes.
            auth (Tuple[str, str]): Optional authentication credentials.

        Returns:
            Union[Generator, bool]: A generator yielding file chunks if successful, False on error.
        """
        try:
            response = requests.get(url, stream=True, auth=auth)
            response.raise_for_status()
            return response.iter_content(chunk_size=chunk_size)
        except requests.RequestException as e:
            warnings.warn(f'Error downloading the file: {e}')
            return False
