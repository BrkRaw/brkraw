import re
import numpy as np
from collections import OrderedDict
from .parser import Parser, ptrn_comment, PARAMETER, HEADER


class Parameter:
    """
    Paravision Parameter object

    This class extends the Parser class and provides methods to initialize the object with a stringlist of parameter dictionaries, retrieve the parameters and headers, and process the contents of the data.

    Args:
        stringlist: A list of strings containing the parameter dictionaries.

    Examples:
        >>> stringlist = ["param1", "param2"]
        >>> parameter = Parameter(stringlist)

    Attributes:
        parameters (property): Get the parameters of the data.
        headers (property): Get the headers of the data.

    Methods:
        _process_contents: Process the contents of the data based on the given parameters.
        _set_param: Set the parameters and headers based on the given data.
    """
    def __init__(self, stringlist, name, scan_id=None, reco_id=None):
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
        if '_' in self._name:
            return ''.join([s.capitalize() for s in self._name.split('_')])
        return self._name.capitalize()

    @property
    def parameters(self):
        """
        Get the parameters of the data.

        Returns:
            OrderedDict: The parameters of the data.

        Examples:
            This property can be accessed directly on an instance of the class to retrieve the parameters.
        """
        return self._parameters

    @property
    def header(self):
        """
        Get the headers of the data.

        Returns:
            OrderedDict: The headers of the data.

        Examples:
            This property can be accessed directly on an instance of the class to retrieve the headers.
        """
        return self._header

    def _process_contents(self, contents, addr, addr_diff, index, value):
        """
        Process the contents of the data based on the given parameters.

        Args:
            contents: The contents of the data.
            addr: The address of the current parameter.
            addr_diff: The difference in addresses between parameters.
            index: The index of the current parameter.
            value: The value of the current parameter.

        Returns:
            tuple: A tuple containing the processed data and its shape.

        Examples:
            This method is intended to be called internally within the class and does not have direct usage examples.
        """
        if addr_diff[index] > 1:
            c_lines = contents[(addr + 1):(addr + addr_diff[index])]
            data = " ".join([line.strip() for line in c_lines if not re.match(ptrn_comment, line)])
            return (data, value) if data else (Parser.convert_string_to(value), -1)
        return Parser.convert_string_to(value), -1

    def _set_param(self, params, param_addr, contents):
        """
        Set the parameters and headers based on the given data.

        Args:
            params: A list of parameter information.
            param_addr: The addresses of the parameters.
            contents: The contents of the data.

        Raises:
            ValueError: If an invalid dtype is encountered.

        Examples:
            This method is intended to be called internally within the class and does not have direct usage examples.
        """
        addr_diff = np.diff(param_addr)
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
        return self.parameters[key]
    
    def __getattr__(self, key):
        return self.parameters[key]
    
    def __repr__(self):
        return f"{self.name}({', '.join(self._repr_items)})"

    def keys(self):
        return self.parameters.keys()
    
    def values(self):
        return self.parameters.values()
    
    def get(self, key):
        if key in self.keys():
            return self.parameters[key]
        else:
            return None
        
    def is_parameter(self):
        return True if self.header else False
        