"""Initialization for the fetcher module.

This module consolidates various fetching functionalities and exposes the Snippets class
for fetching and managing snippets from local and remote sources.

Exposes:
    SnippetsFetcher: A class derived from the Snippets module, tailored to handle the fetching,
                     storage, and synchronization of code snippets or configurations from
                     designated sources.
"""

from .snippets import Snippets as SnippetsFetcher

__all__ = ['SnippetsFetcher']