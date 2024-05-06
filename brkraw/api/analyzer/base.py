"""Base components for data analysis.

This module provides foundational classes and utilities that are shared across different
analyzers within the helper module. These components serve as the base for more specialized
data processing and analysis tasks.
"""

class BaseAnalyzer:
    """A base class providing common functionalities for data analyzers.

    This class serves as a parent to various specialized analyzers, providing shared methods
    and utility functions to assist in data analysis tasks.

    Methods:
        to_dict: Returns a dictionary representation of the instance's attributes.
    """
    def to_dict(self):
        """Convert the analyzer's attributes to a dictionary format.

        Returns:
            dict: A dictionary containing all attributes of the analyzer instance.
        """
        return self.__dict__