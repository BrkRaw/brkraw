"""BaseSnippet for provide platform for developing Snippet to configure and/or interface with other apps in BrkRaw ecosystem.
The current base is minimal structure as currently only PluginSnippet is available, will be expended to contains shared 
method and attributes for Snippet classes
"""

from brkraw.api.config.fetcher.base import Fetcher


class Snippet(Fetcher):
    name: str
    version: str
    type: str
    is_valid: bool
