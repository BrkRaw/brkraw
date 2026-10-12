"""
Parameter parsing and conversion utilities for Bruker Paravision datasets.

This module provides the `Parameters` class, a high-level object that loads
and converts Paravision JCAMP-DX formatted scan parameter files (e.g., `method`,
`acqp`, `reco`). It parses raw JCAMP-DX text into structured Python types,
applies normalization rules (including repeat encodings, symbolic references,
and ndarray reshaping), and exposes each parameter as a Python attribute for
object-oriented access.

The module additionally includes:
- Automatic detection and formatting of numeric arrays.
- Expansion of Bruker-style @N*(x) repeat encodings.
- Special handling of symbolic references in `<...>` notation.
- Conversion of multi-dimensional JCAMP structures into Python tuples or
  NumPy ndarrays.
- A smoke test utility to validate all `.jdx` fixture files.

This module forms a central part of `brkraw.core`, enabling downstream users
to interact with Paravision metadata reliably and idiomatically in Python.
"""
from __future__ import annotations

import logging
from collections import OrderedDict
import io
from pathlib import Path
from typing import IO, Optional, Any, Union, Tuple, Literal, List, Dict, Mapping
import numpy as np
import json
from .jcamp import parse_jcamp

logger = logging.getLogger(__name__)

# Only the head of a file is needed to tell JCAMP text from binary data.
JCAMP_SNIFF_BYTES = 65536


class Parameters:
    _header: OrderedDict
    _store: OrderedDict
    _path: Optional[Path]
    _comments: List[str]
    _exceptions: List[str]
    _format: Optional[dict]
    _source: Union[Path, str, IO[bytes], bytes, bytearray]
    _source_bytes: bytes

    def __init__(
        self,
        source: Union[Path, str, IO[bytes], bytes, bytearray],
        format_registry: Optional[dict] = None,
    ):
        normalized_source, preview_bytes = self._normalize_source(source)

        self._path = Path(source) if isinstance(source, (str, Path)) else None
        self._source = normalized_source
        self._source_bytes = preview_bytes

        try:
            parsed_data = parse_jcamp(self._source)
        except Exception as exc:
            raise ValueError("Source does not look like JCAMP-DX content.") from exc

        self._formatting(parsed_data, format_registry)

    @property
    def source(self):
        return self._source_bytes.decode("utf-8").split("\n")

    @staticmethod
    def _normalize_source(
        source: Union[Path, str, IO[bytes], bytes, bytearray]
    ) -> Tuple[Union[Path, str, IO[bytes], bytes, bytearray], bytes]:
        """Return a parseable source plus a byte preview for JCAMP detection."""
        # Path string that points to a real file
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(path)
            data = path.read_bytes()
            return source, data

        # Raw bytes
        if isinstance(source, (bytes, bytearray)):
            data_bytes = bytes(source)
            return data_bytes, data_bytes

        # File-like
        if hasattr(source, "read"):
            raw = source.read()  # type: ignore[attr-defined]
            if hasattr(source, "seek"):
                try:
                    source.seek(0)  # type: ignore[call-arg,attr-defined]
                except Exception:
                    pass
            if isinstance(raw, (bytes, bytearray)):
                data_bytes = bytes(raw)
            else:
                data_bytes = str(raw).encode("utf-8", errors="ignore")
            return io.BytesIO(data_bytes), data_bytes

        raise TypeError(f"Unsupported source type: {type(source)}")

    def edit_source(
        self,
        source: Union[str, bytes, bytearray],
        *,
        reparse: bool = True,
        format_registry: Optional[dict] = None,
    ) -> None:
        """Replace the underlying JCAMP source and optionally reparse.

        Args:
            source: New JCAMP content as text or bytes.
            reparse: When True, rebuild parsed header/params from the new content.
            format_registry: Optional formatter overrides for reparse.
        """
        if isinstance(source, str):
            data = source.encode("utf-8")
        else:
            data = bytes(source)

        self._source = io.BytesIO(data)
        self._source_bytes = data

        if reparse:
            try:
                parsed_data = parse_jcamp(self._source)
            except Exception as exc:
                raise ValueError("Source does not look like JCAMP-DX content.") from exc
            self._formatting(parsed_data, format_registry or self._format)

    def save_to(self, path: Union[Path, str]) -> Path:
        """Write the current source bytes to a new file."""
        out_path = Path(path)
        out_path.write_bytes(self._source_bytes)
        return out_path

    def source_text(self) -> str:
        """Return the current JCAMP source as text."""
        return self._source_bytes.decode("utf-8", errors="ignore")

    def replace_value(self, key: str, value: Optional[str], *, reparse: bool = True) -> None:
        """Replace a JCAMP parameter block with a raw JCAMP value string."""
        self.replace_values({key: value}, reparse=reparse)

    def replace_values(self, updates: Mapping[str, Optional[str]], *, reparse: bool = True) -> None:
        """Replace multiple JCAMP parameter blocks with raw JCAMP value strings."""
        text = self._source_bytes.decode("utf-8", errors="ignore")
        updated_text = _edit_jcamp_text(text, updates)
        self.edit_source(updated_text, reparse=reparse, format_registry=self._format)

    @staticmethod
    def _looks_like_jcamp(data: bytes) -> bool:
        """Heuristic: check for JCAMP-style header lines in the first JCAMP_SNIFF_BYTES bytes."""
        try:
            text = data[:JCAMP_SNIFF_BYTES].decode("utf-8", errors="ignore")
        except Exception:
            return False

        header_seen = 0
        for line in text.splitlines()[:50]:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("##"):
                header_seen += 1
                if "=" in stripped:
                    return True
            if header_seen >= 2:
                return True
        return False

    @property
    def header(self) -> Optional[OrderedDict]:
        return self._header
    
    @property
    def path(self) -> Optional[Path]:
        return self._path
    
    @staticmethod
    def _get_params(parsed: dict) -> OrderedDict:
        """Extract the parameter dictionary from the JCAMP parse result.

        Args:
            parsed (dict): Result dictionary returned by `parse_jcamp_from_path`.
                Expected to contain a "params" key.

        Returns:
            OrderedDict: Mapping of parameter keys to dictionaries containing
            `shape` and `data`.
        """
        return parsed['params']
    
    @staticmethod
    def _is_at_repeat_param(data: Any) -> bool:
        """Check whether a data field uses Bruker @N*(x) repeat encoding.

        Bruker JCAMP format sometimes encodes repeated values as:
            ["@128*", value]

        Args:
            data (Any): Parsed JCAMP data field.

        Returns:
            bool: True if the field uses @N*(x) encoding, False otherwise.
        """
        if not isinstance(data, list) or not data:
            return False
        shape_hint = data[0]
        if not isinstance(shape_hint, str):
            return False
        return shape_hint.startswith('@') and shape_hint.endswith('*')
    
    @staticmethod
    def _is_array(value: dict) -> bool:
        """Determine whether the given JCAMP value can be converted to a NumPy array.

        Args:
            value (dict): Dictionary with keys "shape" and "data".

        Returns:
            bool: True if `np.asarray(data).reshape(shape)` succeeds.
        """
        try:
            Parameters._get_reshaped_value(value)
            return True
        except Exception:
            return False
    
    @staticmethod
    def _is_symbolic_ref_list(value: dict) -> bool:
        """Identify symbolic-reference lists encoded with JCAMP shapes.

        Paravision sometimes encodes object reference lists as:
            shape = (N, M)
            data = ["<RefA>", "<RefB>", ...]

        The second dimension often corresponds to character length and should be ignored.

        Args:
            value (dict): Dictionary containing JCAMP `shape` and `data`.

        Returns:
            bool: True when the field represents a symbolic reference list.
        """
        shape = value.get("shape")
        data = value.get("data")

        # Must have a 2D shape tuple, e.g. (2, 65)
        if not isinstance(shape, tuple) or len(shape) != 2:
            return False

        # Data must be a list of strings
        if not isinstance(data, list) or not data:
            return False

        # First dimension should match the number of elements
        if shape[0] != len(data):
            return False

        # All elements must be angle-bracketed strings: <...>
        for item in data:
            if not isinstance(item, str):
                return False
            s = item.strip()
            if not (s.startswith("<") and s.endswith(">")):
                return False
        return True

    @staticmethod
    def _get_reshaped_value(value: dict) -> Union[np.ndarray, str]:
        """Convert JCAMP numeric data into a NumPy ndarray with the given shape.

        Args:
            value (dict): Dictionary with "shape" and "data" keys.

        Returns:
            np.ndarray or str: Reshaped ndarray, or raw string when reshaping
            is inappropriate.
        """
        if isinstance(value['data'], str):
            return value['data']
        else:
            return np.asarray(value['data']).reshape(value['shape'])

    @staticmethod
    def _to_string_value(value):
        """Convert JCAMP header values into readable strings.

        Handles:
            - Plain strings
            - Scalars (int, float, NumPy scalar)
            - Flat lists (joined by space)
            - Nested lists (joined by semicolons)

        Args:
            value: Raw parsed JCAMP header content.

        Returns:
            str: Human-readable string representation.
        """
        # CASE 1: already a string
        if isinstance(value, str):
            return value

        # CASE 2: scalar (int, float, numpy scalar, etc.)
        if isinstance(value, (int, float)):
            return str(value)

        # CASE 3: list (flat or nested)
        if isinstance(value, list):
            # Check if this is a nested list (list of lists)
            has_nested = any(isinstance(item, list) for item in value)

            if has_nested:
                # Nested case: join inner lists as phrases, then join phrases with semicolons
                parts = []
                for item in value:
                    if isinstance(item, list):
                        parts.append(" ".join(str(x) for x in item))
                    else:
                        parts.append(str(item))
                return "; ".join(parts)
            else:
                # Flat case: simply join all elements with spaces
                return " ".join(str(item) for item in value)

        # Fallback for any unexpected type
        return str(value)

    @staticmethod
    def _to_json_compatible(obj):
        """Convert internal parameter values into JSON compatible types.

        This normalizes nested containers and special types such as:

        - numpy.ndarray -> list
        - numpy scalar  -> Python scalar
        - tuple         -> list
        - Path          -> str
        - OrderedDict   -> plain dict (order preserved by insertion)
        """
        import numpy as np
        from pathlib import Path
        from collections import OrderedDict

        # Primitive JSON types
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj

        # NumPy arrays and scalars
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()

        # Paths
        if isinstance(obj, Path):
            return str(obj)

        # Dict-like
        if isinstance(obj, (dict, OrderedDict)):
            return {
                str(k): Parameters._to_json_compatible(v)
                for k, v in obj.items()
            }

        # Sequences
        if isinstance(obj, (list, tuple)):
            return [Parameters._to_json_compatible(v) for v in obj]

        # Fallback - last resort stringification
        return str(obj)

    def _formatting(self, parsed_data: dict, format_registry: Optional[dict] = None):
        """Parse and normalize all JCAMP parameters into structured objects.

        This method:
        - Loads JCAMP text using `parse_jcamp` (path, bytes, or file-like).
        - Stores human-readable headers in `_header`.
        - Normalizes all `$Param` fields via `_format_param_value`.
        - Applies any user-provided `format_registry` to specific parameters.
        - Populates `_exceptions` with any inconsistencies or formatting warnings.

        Args:
            format_registry (dict, optional):
                Mapping of parameter names to custom formatting callables.
                Each callable must accept the raw JCAMP `{shape, data}` dict and return
                a normalized Python value.
        """
        self._format = format_registry
        self._header = OrderedDict()
        self._store = OrderedDict()
        self._comments = parsed_data["comments"]
        self._exceptions = parsed_data["exceptions"]

        for key, value in self._get_params(parsed_data).items():
            key_str = str(key)

            # Header style parameters (no leading $)
            if not key_str.startswith("$"):
                self._header[key_str] = self._to_string_value(value["data"])
                continue

            # Parameter style: drop leading $
            param_key = key_str[1:]

            # 1) Custom formatter from registry has priority
            if self._format and param_key in self._format:
                formatted = self._format[param_key](value)
            else:
                formatted = self._format_param_value(param_key, value)

            self._store[param_key] = formatted

    def _format_param_value(self, param_key: str, value: dict):
        """Normalize a single JCAMP parameter into a Python object.

        Handles the full hierarchy of JCAMP transformation logic:
        - Raw values when `shape` is None.
        - Expansion of @N*(x) repeat encodings.
        - Conversion into ndarray when shape and data permit.
        - Tuple conversion for 1D shapes.
        - Special-case formatting of symbolic reference lists (`<...>` tokens).
        - Recording of mismatched shapes or incomplete formatting states.

        Args:
            param_key (str): Name of the JCAMP parameter (without leading `$`).
            value (dict): JCAMP `{"shape": tuple or None, "data": raw}` structure.

        Returns:
            Any: A normalized Python type such as:
                - scalar
                - tuple
                - list
                - np.ndarray
                - or a fallback raw structure (with warnings in `_exceptions`)
        """
        shape = value.get("shape")
        data: Any = value.get("data")

        # No shape metadata: just return raw data
        if shape is None:
            return data
        if data is None:
            return shape

        # Expand @N*(x) repeat encoding if present
        if self._is_at_repeat_param(data):
            repeat_spec = data[0]      # e.g. "@128*"
            elem = data[1]
            try:
                repeat_count = int(repeat_spec[1:-1])
                data = [elem] * repeat_count
                value = {"shape": shape, "data": data}
            except Exception as exc:
                msg = (
                    f"Failed to expand repeat encoding for '{param_key}': "
                    f"{repeat_spec!r} -> {exc!r}"
                )
                self._exceptions.append(msg)
                return data

        # Try to treat as a proper numpy array
        array_candidate = {"shape": shape, "data": data}
        if self._is_array(array_candidate):
            return self._get_reshaped_value(array_candidate)

        # Fallback: handle simple 1D shapes as tuple
        if isinstance(shape, tuple) and len(shape) == 1:
            expected_len = shape[0]

            # Shape of length 1: treat as scalar-like / struc
            if expected_len == 1:
                return data

            # Shape of length N: treat as N element tuple
            tup = tuple(data)
            if len(tup) != expected_len:
                msg = (
                    f"Shape mismatch in parameter '{param_key}': "
                    f"expected length {expected_len}, got {len(tup)}"
                )
                self._exceptions.append(msg)
            return tup
        if self._is_symbolic_ref_list(value):
            return np.asarray(value["data"])

        # Any other complex shape that could not be reshaped
        # Return data as is but record that formatting was incomplete
        msg = (
            f"Could not format parameter '{param_key}' with shape {shape!r}; "
            f"leaving raw data."
        )
        self._exceptions.append(msg)
        return data

    def __getitem__(self, key):
        """Dictionary-style access to parsed parameters."""
        return self._store[key]

    def __setitem__(self, key, value):
        self._store[key] = value

    def __getattr__(self, key):
        """Attribute-style access to parsed parameters.

        Raises:
            AttributeError: When the parameter does not exist.
        """
        try:
            return self._store[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key: str, value):
        if key.startswith("_"):
            super().__setattr__(key, value)
        else:
            self._store[key] = value

    def keys(self):
        """Return all available parameter names."""
        return self._store.keys()

    def search_keys(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
        include_header: bool = True,
        include_params: bool = True,
        match_mode: Literal["substring", "exact"] = "substring",
    ) -> List[Dict[str, Any]]:
        """Search parameter and header entries and return matching key-value pairs.

        Args:
            query (str):
                Substring to search for inside keys.
            case_sensitive (bool, optional):
                When True, match is case sensitive.
                When False (default), keys and query are compared in lowercase.
            include_header (bool, optional):
                Search inside header keys as well (default: True).
            include_params (bool, optional):
                Search inside parameter keys (default: True).
            match_mode ({"substring", "exact"}, optional):
                Whether to search by substring (default) or exact key match.

        Returns:
            List[Dict[str, Any]]: A list of single-entry dictionaries containing
            matching keys and their values, preserving header-first order.
        """
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        if match_mode not in {"substring", "exact"}:
            raise ValueError("match_mode must be 'substring' or 'exact'")

        # Prepare comparable query
        if not case_sensitive:
            query_cmp = query.lower()
        else:
            query_cmp = query

        matches: List[Dict[str, Any]] = []

        def collect_matches(source: OrderedDict):
            for key, value in source.items():
                key_cmp = key.lower() if not case_sensitive else key
                is_match = (
                    query_cmp in key_cmp if match_mode == "substring" else query_cmp == key_cmp
                )
                if is_match:
                    matches.append({key: value})

        # Search in header
        if include_header:
            collect_matches(self._header)

        # Search in parameters (_store)
        if include_params:
            collect_matches(self._store)

        return matches

    def get(self, key: str, default=None):
        """Return the value for key if present, else default."""
        if key in self._store:
            return self._store[key]
        if key in self._header:
            return self._header[key]
        return default

    def to_json(self, path: Optional[Union[Path, str]] = None, *, indent: int = 2) -> str:
        """Serialize the current Parameters object to a JSON string and optionally file.

        The JSON payload includes:
        - path: Source JCAMP file path as string.
        - header: Normalized header entries.
        - params: Parsed and formatted parameter values.
        - comments: JCAMP comment lines (without `$$`).
        - exceptions: Collected parsing or formatting warnings.

        Args:
            path (Path or str, optional):
                Output file path. When provided, the JSON string is written to
                this location.
            indent (int, optional):
                Indentation level passed to `json.dumps` for pretty printing.

        Returns:
            str: The serialized JSON string representing this Parameters object.
        """
        payload = {
            "path": str(self._path) if hasattr(self, "_path") else None,
            "header": self._to_json_compatible(self._header),
            "params": self._to_json_compatible(self._store),
            "comments": list(self._comments or []),
            "exceptions": list(self._exceptions or []),
        }

        text = json.dumps(payload, indent=indent, sort_keys=False)

        if path is not None:
            out_path = Path(path)
            out_path.write_text(text, encoding="utf-8")

        return text


def run_smoke_test(
    fixtures_dir: Path,
    format_registry: Optional[dict] = None,
) -> dict:
    """Execute a smoke test over all JCAMP `.jdx` files in a directory.

    The smoke test ensures:
      - Parameters objects can be constructed without raising errors.
      - JCAMP `_exceptions` are recorded for problematic fields.
      - No raw JCAMP values with unprocessed `{"shape": ..., "data": ...}` remain.
      - All parameters are accessible as Python attributes.
      - Diagnostics are logged for initialization failures, shape mismatches,
        symbolic reference issues, or incomplete conversions.

    Args:
        fixtures_dir (Path):
            Directory containing one or more `.jdx` JCAMP test files.
        format_registry (dict, optional):
            Optional mapping of parameter names to custom formatting functions.

    Returns:
        dict: Summary of smoke-test results with the following keys:

            - total_files (int): Count of `.jdx` files processed.
            - ok_files (List[Path]): Files fully validated without issues.
            - exception_files (List[Tuple[str, List[str]]]):
                  Files with JCAMP parser-generated `_exceptions`.
            - init_error_files (List[Tuple[str, str]]):
                  Files that failed to initialize a Parameters object.
            - raw_value_params (List[Tuple[str, str]]):
                  Parameters that remained in raw `{"shape":..., "data":...}` form.
            - attr_access_errors (List[Tuple[str, str, str]]):
                  Attribute-access failures `(file, key, error)`.

    """
    summary = {
        "total_files": 0,
        "ok_files": [],
        "exception_files": [],      # (file, exceptions)
        "init_error_files": [],     # (file, repr(exc))
        "raw_value_params": [],     # (file, param_key)
        "attr_access_errors": [],   # (file, param_key, repr(exc))
    }

    for jdx_path in sorted(fixtures_dir.glob("*.jdx")):
        summary["total_files"] += 1
        logger.info(f"Checking {jdx_path}")
        file_str = jdx_path.as_posix()

        try:
            params = Parameters(jdx_path, format_registry=format_registry)
        except Exception as exc:
            logger.error(f"Failed to initialize Parameters for {file_str}: {exc}")
            summary["init_error_files"].append((file_str, repr(exc)))
            continue

        file_has_exceptions = False
        file_has_raw_values = False
        file_has_attr_errors = False

        # 1) Check recorded parse exceptions from jcamp/parser layer
        if getattr(params, "_exceptions", None):
            file_has_exceptions = True
            logger.warning(
                f"Found {len(params._exceptions)} exceptions in {file_str}"
            )
            summary["exception_files"].append((file_str, params._exceptions))

        # 2) Check for leftover raw dict values with 'shape' key in _store
        for key, val in params._store.items():
            if isinstance(val, dict) and "shape" in val:
                file_has_raw_values = True
                logger.error(
                    f"Parameter '{key}' in {file_str} still has a raw dict value with 'shape'"
                )
                summary["raw_value_params"].append((file_str, key))

        # 3) Check that every key is accessible as an attribute
        for key in list(params._store.keys()):
            try:
                attr_val = getattr(params, key)
                # Optional: ensure attribute value matches stored value
                if attr_val is not params._store[key]:
                    # This is not necessarily an error, but you can log if you care.
                    logger.debug(
                        f"Attribute '{key}' in {file_str} does not match _store by identity"
                    )
            except Exception as exc:
                file_has_attr_errors = True
                logger.error(
                    f"Attribute access failed for '{key}' in {file_str}: {exc}"
                )
                summary["attr_access_errors"].append((file_str, key, repr(exc)))

        # 4) Mark file as fully OK only if no issues were detected
        if not (file_has_exceptions or file_has_raw_values or file_has_attr_errors):
            summary["ok_files"].append(jdx_path)

    return summary


def _edit_jcamp_text(text: str, updates: Mapping[str, Optional[str]]) -> str:
    if not updates:
        return text
    pending = set(updates.keys())
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("##$"):
            key = line[3:].split("=", 1)[0].strip()
            block_start = i
            i += 1
            while i < len(lines) and not lines[i].startswith("##"):
                i += 1
            block_lines = lines[block_start:i]
            if key in updates:
                pending.discard(key)
                new_value = updates[key]
                if new_value is None:
                    continue
                out.extend(_format_param_block(key, new_value))
            else:
                out.extend(block_lines)
            continue
        out.append(line)
        i += 1
    if pending:
        logger.debug("JCAMP update keys not found: %s", sorted(pending))
    return "".join(out)


def _format_param_block(key: str, value: str) -> List[str]:
    value = value.rstrip("\n")
    lines = value.splitlines()
    if not lines:
        return [f"##${key}= \n"]
    out = [f"##${key}= {lines[0]}\n"]
    if len(lines) > 1:
        out.extend([line + "\n" for line in lines[1:]])
    return out


__all__ = [
    'Parameters',
    'run_smoke_test',
]

def __dir__() -> List[str]:
    return sorted(__all__)
