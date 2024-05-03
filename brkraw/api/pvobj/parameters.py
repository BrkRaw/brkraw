"""Provides functionality for parsing and managing parameter metadata within Paravision datasets.

This module includes the `Parameter` class, which extends the functionalities of a generic `Parser` class. 
It specifically handles the extraction and management of parameter data and header information from strings 
that represent parameter dictionaries in Paravision datasets. 
These capabilities are critical for accessing and manipulating the underlying data in a structured and interpretable format.

Classes:
    Parameter: A class designed to parse and manage parameter dictionaries, providing access to parameters and headers, 
               processing content data, and setting parameter values based on input data.

Dependencies:
    re: Regular expression operations for parsing and processing text.
    numpy: Provides support for large, multi-dimensional arrays and matrices, 
           along with a large collection of high-level mathematical functions to operate on these arrays.
    OrderedDict: A dictionary subclass that remembers the order in which its contents are added, 
                 used for maintaining an ordered set of parameters.
"""

from __future__ import annotations
import re
import numpy as np
from collections import OrderedDict
from .parser import Parser, ptrn_comment, PARAMETER, HEADER
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional
    from typing import List
    from numpy.typing import NDArray


class Parameter:
    """Handles the parsing and management of parameter data for Paravision experiments.

    This class extends the Parser class, utilizing its functionalities to interpret a list of string 
    representations of parameter dictionaries, manage parameter and header information, and process the contents of the data.

    Args:
        stringlist (List[str]): A list of strings containing parameter entries.
        name (str): The name identifying the parser object.
        scan_id (Optional[int]): The scan ID associated with the parameter data.
        reco_id (Optional[int]): The reconstruction ID associated with the parameter data.

    Attributes:
        _parameters (OrderedDict): Stores parameter values.
        _header (OrderedDict): Stores header information.
        _name (str): Name of the parser object.
        _repr_items (List[str]): List of string representations for object description.
    """
    def __init__(self, 
                 stringlist: List[str], 
                 name: str, 
                 scan_id: Optional[int] = None, 
                 reco_id: Optional[int] = None):
        """
        Initialize the Parameter object with the given stringlist, name, scan_id, and reco_id.

        Args:
            stringlist: A list of strings containing the parameter dictionaries.
            name: The name of the Parser object.
            scan_id: The scan ID associated with the Parser object.
            reco_id: The reco ID associated with the Parser object.

        Examples:
            >>> stringlist = ["param1", "param2"]
            >>> name = "MyParser"
            >>> scan_id = 12345
            >>> reco_id = 67890
            >>> parser = Parser(stringlist, name, scan_id, reco_id)
        """
        self._name = name
        self._repr_items = []
        if scan_id:
            self._repr_items.append(f'scan_id={scan_id}')
        if reco_id:
            self._repr_items.append(f'reco_id={reco_id}')
        self._set_param(*Parser.load_param(stringlist))

    @property
    def name(self):
        """Get a formatted name of the parser object, capitalizing each part separated by underscores.

        Returns:
            str: A capitalized version of the name attribute.
        """
        if '_' in self._name:
            return ''.join([s.capitalize() for s in self._name.split('_')])
        return self._name.capitalize()

    @property
    def parameters(self):
        """Retrieve the parameters processed by the parser.

        Returns:
            OrderedDict: A dictionary containing the parameters of the data.
        """
        return self._parameters

    @property
    def header(self):
        """Retrieve the headers processed by the parser.

        Returns:
            OrderedDict: A dictionary containing the headers of the data.
        """
        return self._header

    def _process_contents(self, 
                          contents: List[str], 
                          addr: int, 
                          addr_diff: NDArray, 
                          index: int, 
                          value: str):
        """Process the data contents based on parameter addresses and differences.

        Args:
            contents (List[str]): The full list of content strings.
            addr (int): The current parameter's address in contents.
            addr_diff (numpy.ndarray): An array of address differences between parameters.
            index (int): The index of the current parameter.
            value (str): The initial value of the parameter.

        Returns:
            tuple: A tuple containing the processed data as a string and its shape or format as int.
        """
        if addr_diff[index] > 1:
            c_lines = contents[(addr + 1):(addr + addr_diff[index])]
            data = " ".join([line.strip() for line in c_lines if not re.match(ptrn_comment, line)])
            return (data, value) if data else (Parser.convert_string_to(value), -1)
        return Parser.convert_string_to(value), -1

    def _set_param(self, 
                   params: List[tuple], 
                   param_addr: List[int], 
                   contents: List[str]):
        """Initialize parameters and headers from parsed data.

        Args:
            params (List[tuple]): List containing parameter tuples (dtype, key, value).
            param_addr (List[int]): List of addresses where parameters are located in the content.
            contents (List[str]): The contents as a list of strings from which to extract data.

        Raises:
            ValueError: If an invalid data type (dtype) is encountered.
        """
        addr_diff = np.diff(param_addr)
        self._params_key_struct = params
        self._contents = contents
        self._header = OrderedDict()
        self._parameters = OrderedDict()
        for index, addr in enumerate(param_addr[:-1]):
            dtype, key, value = params[addr]
            data, shape = self._process_contents(contents, addr, addr_diff, index, value)
            if dtype is PARAMETER:
                self._parameters[key] = Parser.convert_data_to(data, shape)
            elif dtype is HEADER:
                self._header[key] = data
            else:
                raise ValueError("Invalid dtype encountered in '_set_param'")

    def __getitem__(self, key):
        """Allows dictionary-like access to parameters.

        Args:
            key (str): The key for the desired parameter.

        Returns:
            The value associated with the key in the parameters dictionary.
        """
        return self.parameters[key]
    
    def __getattr__(self, key):
        """Allows attribute-like access to parameters.

        Args:
            key (str): The key for the desired parameter.

        Returns:
            The value associated with the key in the parameters dictionary.
        """
        return self.parameters[key]
    
    def __repr__(self):
        """Provide a string representation of the Parameter object for debugging and logging.

        Returns:
            str: A string representation of the object.
        """
        return f"{self.name}({', '.join(self._repr_items)})"

    def keys(self):
        """Get the keys of the parameters dictionary.

        Returns:
            KeysView: A view of the keys in the parameter dictionary.
        """
        return self.parameters.keys()
    
    def values(self):
        """Get the values of the parameters dictionary.

        Returns:
            ValuesView: A view of the values in the parameter dictionary.
        """
        return self.parameters.values()
    
    def items(self):
        """Get the key and value pairs of the parameters dictionary.

        Returns:
            ItemView: A view of the values in the parameter dictionary.
        """
        return self.parameters.items()
    
    def get(self, key: str):
        """Get the value of a parameter by key, returning None if the key is not found.

        Args:
            key (str): The key for the desired parameter.

        Returns:
            The value associated with the key if it exists, otherwise None.
        """
        if key in self.keys():
            return self.parameters[key]
        else:
            return None
        
    def is_parameter(self):
        """True if data successfully loaded"""
        return True if self.header else False
        