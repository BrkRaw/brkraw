from .utils import *


class Parameter():
    def __init__(self, stringlist):
        # parse the parameter dictionaries from stringlist
        self._set_param(*load_param(stringlist))

    @property
    def parameters(self):
        return self._parameters

    @property
    def headers(self):
        return self._headers

    def _set_param(self, params, param_addr, contents):
        # get distance between each parameter
        addr_diff = np.diff(param_addr)

        # for debugging
        self._contents = contents
        # build dictionary for parameters
        self._headers = OrderedDict()
        self._parameters = OrderedDict()
        for index, addr in enumerate(param_addr[:-1]):
            dtype, key, value = params[addr]
            shape = -1
            # if there are spaces before next parameter apears
            if addr_diff[index] > 1:
                # collect all text within spaces
                c_lines = contents[(addr + 1):(addr + addr_diff[index])]
                # merge lines into single text as data
                data = " ".join([line.strip() for line in c_lines if not re.match(ptrn_comment, line)])
                # no contents in data
                if not data:
                    data = convert_string_to(value)
                else:
                    shape = value
            else:
                data = convert_string_to(value)

            if dtype is PARAMETER:
                self._parameters[key] = convert_data_to(data, shape)
            elif dtype is HEADER:
                self._headers[key] = data
            else:
                raise Exception