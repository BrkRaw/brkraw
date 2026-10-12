"""Read selected indices of a Fortran-ordered raw array from a binary file (WI-0083)."""

import itertools
from typing import Any, Dict, Sequence, Tuple, Union
import numpy as np

def _read_into(f, arr, byte_offset):
    f.seek(byte_offset)
    try:
        view = memoryview(arr).cast("B")
    except (TypeError, ValueError):
        view = memoryview(arr.view(np.uint8))
    
    done = 0
    total_wanted = len(view)
    while done < total_wanted:
        n = f.readinto(view[done:])
        if n is None or n == 0:
            raise ValueError("2dseq truncated: wanted %d bytes at offset %d, got %d" % (total_wanted, byte_offset, done))
        done += n

def read_cube(f, dtype, shape, indices: Dict[int, Sequence[int]]):
    dt = np.dtype(dtype)
    itemsize = dt.itemsize
    shape = tuple(int(n) for n in shape)
    ndim = len(shape)
    
    if ndim < 1:
        # Spec says ndim is at least 1, but for safety
        raise ValueError("ndim must be at least 1")

    sel = []
    for a in range(ndim):
        if a in indices:
            seq = indices[a]
            if len(seq) == 0:
                raise ValueError("empty")
            
            # Validation: strictly increasing, >= 0, < shape[a]
            # Also check if they are plain ints (numpy ints are fine)
            for i in range(len(seq)):
                val = seq[i]
                if not isinstance(val, (int, np.integer)) or isinstance(val, bool):
                    raise ValueError("indices")
                if val < 0 or val >= shape[a]:
                    raise ValueError("indices")
                if i > 0 and val <= seq[i-1]:
                    raise ValueError("indices")
            sel.append(list(seq))
        else:
            sel.append(list(range(shape[a])))

    # Validate indices keys
    for k in indices:
        if not isinstance(k, int) or isinstance(k, bool) or k < 0 or k >= ndim:
            raise ValueError("axis")

    out_shape = tuple(len(s) for s in sel)
    out = np.empty(out_shape, dtype=dt, order="F")
    
    stride = []
    current_stride = 1
    for a in range(ndim):
        stride.append(current_stride)
        current_stride *= shape[a]
    
    # Find smallest axis j where len(sel[a]) != shape[a]
    j = -1
    for a in range(ndim):
        if len(sel[a]) != shape[a]:
            j = a
            break
    
    if j == -1:
        # Everything selected
        flat = out.T.reshape(-1)
        _read_into(f, flat, 0)
        out.flags.writeable = False
        return out
    
    prefix = stride[j] if j >= 0 else 1 # j is always >= 0 here
    
    # Split sel[j] into runs
    runs = []
    if j < ndim:
        s_j = sel[j]
        if s_j:
            start_val = s_j[0]
            pos = 0
            length = 1
            for i in range(1, len(s_j)):
                if s_j[i] == s_j[i-1] + 1:
                    length += 1
                else:
                    runs.append((start_val, pos, length))
                    start_val = s_j[i]
                    pos = i
                    length = 1
            runs.append((start_val, pos, length))

    # Outer axes j+1 .. ndim-1
    outer_axes_ranges = [range(len(sel[a])) for a in range(ndim - 1, j, -1)]
    for p in itertools.product(*outer_axes_ranges):
        # p is (pos_ndim-1, pos_ndim-2, ..., pos_j+1)
        outer_elems = 0
        outer_pos = []
        # p is ordered ndim-1 down to j+1
        # We need to map them back to axes j+1 up to ndim-1
        for idx, pos_val in enumerate(reversed(p)):
            axis_a = j + 1 + idx
            outer_elems += sel[axis_a][pos_val] * stride[axis_a]
            outer_pos.append(pos_val)
            
        for start_value, pos, length in runs:
            n_elem = prefix * length
            elem_offset = outer_elems + start_value * prefix
            chunk = np.empty(n_elem, dtype=dt)
            _read_into(f, chunk, elem_offset * itemsize)
            block = chunk.reshape(tuple(shape[:j]) + (length,), order="F")
            
            # out[(slice(None),) * j + (slice(pos, pos + length),) + tuple(outer_pos)] = block
            # The slice(None) covers axes 0..j-1
            # The slice(pos, pos+length) covers axis j
            # The tuple(outer_pos) covers axes j+1..ndim-1
            idx_tuple = (slice(None),) * j + (slice(pos, pos + length),) + tuple(outer_pos)
            out[idx_tuple] = block
            
    out.flags.writeable = False
    return out
