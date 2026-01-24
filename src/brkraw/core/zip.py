"""
A set of lightweight utilities for working with ZIP archives in-memory and
providing convenient abstractions for files and directories inside a ZIP.

The focus is:
- Safe, Pythonic dataclasses (FileBuffer, ZippedFile, ZippedDir) wrapping
  raw bytes and zipfile.ZipFile entries.
- Support for extracting, isolating, and re-packing subtrees of a ZIP archive
  without touching the filesystem unless explicitly requested.
- Flexible to_filename() dispatcher to persist objects (ZipFile, ZippedDir,
  ZippedFile, BytesIO, or raw bytes) to disk in a normalized way.

Key abstractions
----------------
- FileBuffer
  A simple wrapper around an in-memory BytesIO buffer.
  Provides .bytes() to retrieve raw data and .to_filename() to persist
  directly to disk.

- ZippedFile
  Represents a single file entry inside a ZIP archive.
  Offers .open(), .read(), .buffer(), .isolate() to access content,
  and .extract_to() to write the raw file to disk.

- ZippedDir
  Represents a directory subtree inside a ZIP.
  Provides .isolate() to generate a new ZIP containing only this subtree
  (optionally under a new root directory), .to_filename() to persist it as a
  zip file, and .extract_to() to unpack the subtree to a directory.

- walk()
  Like os.walk, but operates over a zipfile.ZipFile.
  Yields (dirpath, dirnames, fileentries) tuples, where fileentries are
  ZippedFile objects with direct access to contents.

- fetch_files_in_zip() / fetch_dirs_in_zip()
  Helpers for searching within a ZIP by filename or directory name, supporting
  exact match, wildcards, or regex.

- to_filename()
  A generic dispatcher to persist many kinds of in-memory objects. For ZipFile
  and ZippedDir it creates zip archives; for ZippedFile it writes the raw file
  to disk; for bytes/str/BytesIO it writes the raw payload to a file.

Typical usage
-------------
    import zipfile
    from brkraw.core import zip

    # Load a zip from bytes
    zf = zip.bytes_to_zipfile(zip_bytes)

    # Walk the archive
    for dirpath, dirnames, files in zip.walk(zf):
        for f in files:
            print(f.name, len(f.read()))

    # Extract all "config.json" files
    matches = zip.fetch_files_in_zip(zf, "config.json")
    for m in matches:
        buf = m.isolate()   # -> FileBuffer
        buf.to_filename("/tmp/config.json")

    # Isolate a subdirectory into a new in-memory zip
    dirs = zip.fetch_dirs_in_zip(zf, "src")
    if dirs:
        sub = dirs[0]  # ZippedDir
        new_zip = sub.isolate(add_root=True, root_name="package-src")
        with new_zip.open("package-src/module.py") as fh:
            print(fh.read().decode("utf-8"))

        # Optionally persist the isolated zip to disk:
        zip.to_filename(new_zip, "/tmp/package-src.zip")

Design notes
------------

- Uses only the stdlib (zipfile, io, shutil) for maximum portability.
- Preserves timestamps and file permissions (external_attr) where possible.
- Supports both in-memory workflows (BytesIO) and on-disk workflows
  (via extract_to() or the to_filename() dispatcher).
- Explicit directory entries are preserved/added so that GUI ZIP browsers
  behave predictably.

Exports
-------

- FileBuffer
- ZippedFile
- ZippedDir
- walk
- bytes_to_zipfile
- create_from_dir
- load
- fetch_files_in_zip
- fetch_dirs_in_zip
- to_filename
"""

from __future__ import annotations

import fnmatch
import io
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, IO, Iterable, List, Optional, Tuple, Union, Literal, Set

# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


def _ensure_parent_dir(path: Union[str, os.PathLike]) -> str:
    """Ensure parent directory exists and return an absolute path."""
    p = os.fspath(path)
    abs_path = os.path.abspath(p)
    parent = os.path.dirname(abs_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    return abs_path


# ---------------------------------------------------------------------------
# FileBuffer
# ---------------------------------------------------------------------------


@dataclass
class FileBuffer:
    """A simple file buffer object (in-memory or spooled to disk)."""
    name: str
    buffer: IO[bytes]

    def bytes(self) -> bytes:
        """Return full bytes content."""
        pos = self.buffer.tell()
        try:
            self.buffer.seek(0)
            return self.buffer.read()
        finally:
            self.buffer.seek(pos)

    def to_filename(
        self,
        path: Union[str, os.PathLike],
        *,
        overwrite: bool = True,
        makedirs: bool = True,
    ) -> str:
        """Write the buffer content to a file at path.

        Parameters
        ----------
        path : str or os.PathLike
            Destination file path.
        overwrite : bool, optional
            If False and the file exists, raise FileExistsError. Default True.
        makedirs : bool, optional
            If True, create parent directories as needed. Default True.

        Returns
        -------
        str
            The absolute filesystem path written to.
        """
        path = os.fspath(path)
        abs_path = os.path.abspath(path)

        if not overwrite and os.path.exists(abs_path):
            raise FileExistsError(f"File already exists: {abs_path}")

        parent = os.path.dirname(abs_path)
        if makedirs and parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        pos = self.buffer.tell()
        try:
            self.buffer.seek(0)
            with open(abs_path, "wb") as f:
                shutil.copyfileobj(self.buffer, f)
        finally:
            self.buffer.seek(pos)

        return abs_path


# ---------------------------------------------------------------------------
# ZippedFile
# ---------------------------------------------------------------------------


@dataclass
class ZippedFile:
    """A file-like handle to a file inside a ZipFile with convenient accessors."""
    name: str        # basename of the file (e.g., "README.md")
    arcname: str     # archive path inside the zip (e.g., "repo-123/README.md")
    zipobj: zipfile.ZipFile

    def __repr__(self) -> str:
        try:
            info = self.zipobj.getinfo(self.arcname)
            size = info.file_size
        except Exception:
            size = "?"
        return f"ZippedFile(path='{self.arcname}', size={size})"

    def is_dir(self) -> bool:
        return False

    def is_file(self) -> bool:
        return True

    def open(self) -> IO[bytes]:
        """Return a readable file-like object (binary). Caller should close it."""
        return self.zipobj.open(self.arcname, "r")

    def read(self) -> bytes:
        """Read entire file content into bytes."""
        return self.zipobj.read(self.arcname)

    def buffer(self) -> io.BytesIO:
        """Return an in-memory BytesIO buffer holding the file content."""
        return io.BytesIO(self.read())

    def isolate(
        self,
        *,
        buffering: Literal["memory", "spooled"] = "memory",
        max_spool_size: int = 10 * 1024 * 1024,
        cache_dir: Optional[Union[str, os.PathLike]] = None,
    ) -> FileBuffer:
        """Return a FileBuffer for this file content.

        Parameters
        ----------
        buffering : {"memory", "spooled"}, optional
            Use in-memory BytesIO by default. When "spooled", use a
            tempfile.SpooledTemporaryFile that spills to disk past
            max_spool_size to avoid high memory usage.
        max_spool_size : int, optional
            Threshold in bytes before a spooled buffer spills to disk.
        cache_dir : str or os.PathLike, optional
            Directory to place temporary files when buffering="spooled".
        """
        data = self.read()
        if buffering == "spooled":
            spool_dir = os.fspath(cache_dir) if cache_dir is not None else None
            buf = tempfile.SpooledTemporaryFile(max_size=max_spool_size, dir=spool_dir)
            buf.write(data)
            buf.seek(0)
            return FileBuffer(name=self.name, buffer=buf)
        # default: in-memory
        buf = io.BytesIO(data)
        buf.seek(0)
        return FileBuffer(name=self.name, buffer=buf)

    def extract_to(
        self,
        path: Union[str, os.PathLike],
    ) -> str:
        """Extract this file to a filesystem path.

        If `path` is a directory, the file is written under that directory using
        this entry's name. If `path` is a file path, the content is written
        directly to that path. Use `arcname` in the dispatcher to override the
        output name when calling via to_filename().
        """
        return zippedfile_to_filename(self, path)


# ---------------------------------------------------------------------------
# Create zip from directory
# ---------------------------------------------------------------------------


def create_from_dir(
    zip_path: Union[str, os.PathLike],
    source_dir: Union[str, os.PathLike],
    compression: int = zipfile.ZIP_DEFLATED,
) -> str:
    """Create a ZIP archive from the contents of a directory.

    Parameters
    ----------
    zip_path : str or os.PathLike
        The path to the output ZIP file.
    source_dir : str or os.PathLike
        The path to the directory whose contents will be zipped.
    compression : int, optional
        The compression method to use (default: zipfile.ZIP_DEFLATED).

    Returns
    -------
    str
        The absolute path to the created ZIP file.
    """
    zip_path = _ensure_parent_dir(zip_path)
    source_dir = os.fspath(source_dir)

    with zipfile.ZipFile(zip_path, "w", compression=compression) as zf:
        for root, dirs, files in os.walk(source_dir):
            # Add directory entries
            for d in dirs:
                full_path = os.path.join(root, d)
                arcname = os.path.relpath(full_path, source_dir)
                zf.writestr(arcname + "/", b"")
            # Add file entries
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, source_dir)
                zf.write(full_path, arcname)
    return zip_path


# ---------------------------------------------------------------------------
# ZippedDir
# ---------------------------------------------------------------------------


@dataclass
class ZippedDir:
    """Directory-like node inside a ZipFile. Holds subdirectories and files."""
    name: str
    path: str
    dirs: List["ZippedDir"]
    files: List[ZippedFile]

    def __repr__(self) -> str:
        return f"ZippedDir(path='{self.path}', dirs={len(self.dirs)}, files={len(self.files)})"

    def is_dir(self) -> bool:
        return True

    def is_file(self) -> bool:
        return False

    def as_dict(self) -> Dict[str, Any]:
        """Convert to plain dict (for debugging or serialization)."""
        return {
            "name": self.name,
            "path": self.path,
            "dirs": [d.as_dict() for d in self.dirs],
            "files": [f.name for f in self.files],
        }

    def listdir(self) -> List[str]:
        """List immediate children names (dirs first, then files)."""
        dirnames = sorted([d.name for d in self.dirs])
        filenames = sorted([f.name for f in self.files])
        return dirnames + filenames

    def iterdir(self) -> Iterable[Union["ZippedDir", ZippedFile]]:
        """Iterate over children objects (dirs first, then files)."""
        for d in sorted(self.dirs, key=lambda x: x.name):
            yield d
        for f in sorted(self.files, key=lambda x: x.name):
            yield f

    def _resolve_zipobj(self) -> zipfile.ZipFile:
        """Resolve the underlying ZipFile from any child file. Raise if not resolvable."""
        stack: List["ZippedDir"] = [self]
        while stack:
            node = stack.pop()
            for f in node.files:
                return f.zipobj
            stack.extend(node.dirs)
        raise RuntimeError("Cannot resolve ZipFile for this ZippedDir (no files found).")

    def isolate(
        self,
        compression: int = zipfile.ZIP_DEFLATED,
        include_dir_entries: bool = True,
        add_root: bool = False,
        root_name: Union[str, None] = None,
        *,
        buffering: Literal["memory", "spooled"] = "memory",
        max_spool_size: int = 20 * 1024 * 1024,
        cache_dir: Optional[Union[str, os.PathLike]] = None,
    ) -> zipfile.ZipFile:
        """Create a new ZIP containing only this directory subtree.

        By default (add_root=False), the new ZIP root is this directory itself,
        i.e., arcnames are relative to self.path (no extra top-level folder).

        If add_root=True, files are placed under a top-level directory named
        root_name (or self.name if root_name is None). In other words, entries
        will look like "<root_name>/<relative-path-inside-self>".

        Parameters
        ----------
        compression : int, optional
            Zip compression method (default: ZIP_DEFLATED).
        include_dir_entries : bool, optional
            If True, ensure folder entries (for example "a/", "a/b/") exist.
        add_root : bool, optional
            If True, wrap all contents under a top-level directory.
        root_name : Optional[str], optional
            Name of the top-level directory when add_root is True. If None,
            uses self.name.
        buffering : {"memory", "spooled"}, optional
            Storage for the generated zip. "memory" uses BytesIO; "spooled" uses
            tempfile.SpooledTemporaryFile and spills to disk past max_spool_size.
        max_spool_size : int, optional
            Threshold in bytes for spilling to disk when buffering="spooled".
        cache_dir : str or os.PathLike, optional
            Directory for temporary files when buffering="spooled".

        Returns
        -------
        zipfile.ZipFile
            A ZipFile object containing only this subtree.
        """
        src_zip = self._resolve_zipobj()

        # Normalize to POSIX style used inside zip archives
        prefix = self.path.strip("/")
        if prefix:
            prefix = prefix + "/"

        # Decide root folder name when requested
        if add_root:
            root = (root_name or (self.name or "root")).strip("/")
            root_prefix = f"{root}/"
        else:
            root_prefix = ""

        if buffering == "spooled":
            spool_dir = os.fspath(cache_dir) if cache_dir is not None else None
            out_buf: IO[bytes] = tempfile.SpooledTemporaryFile(
                max_size=max_spool_size, dir=spool_dir
            )
        else:
            out_buf = io.BytesIO()

        with zipfile.ZipFile(out_buf, "w", compression=compression) as out_zip:
            # Optional explicit top-level root
            if add_root and include_dir_entries:
                ri = zipfile.ZipInfo(root_prefix)
                ri.external_attr = (0o40755 << 16)
                out_zip.writestr(ri, b"")

            # Copy all entries whose filename starts with the directory prefix
            for info in src_zip.infolist():
                fn = info.filename
                if not fn.startswith(prefix):
                    continue

                rel = fn[len(prefix):]
                if not rel:
                    continue

                if add_root:
                    arcname = root_prefix + rel
                else:
                    arcname = rel

                if arcname.endswith("/"):
                    if include_dir_entries:
                        dir_info = zipfile.ZipInfo(arcname)
                        dir_info.date_time = info.date_time
                        dir_info.external_attr = (0o40755 << 16)
                        out_zip.writestr(dir_info, b"")
                    continue

                data = src_zip.read(info.filename)
                new_info = zipfile.ZipInfo(arcname)
                new_info.date_time = info.date_time
                new_info.external_attr = info.external_attr
                out_zip.writestr(new_info, data)

            if include_dir_entries:
                written = set(out_zip.namelist())
                need_dirs = set()
                for name in written:
                    if name.endswith("/"):
                        continue
                    parts = name.split("/")[:-1]
                    cur = []
                    for p in parts:
                        cur.append(p)
                        need_dirs.add("/".join(cur) + "/")

                for d in sorted(need_dirs):
                    if d not in written:
                        di = zipfile.ZipInfo(d)
                        di.external_attr = (0o40755 << 16)
                        out_zip.writestr(di, b"")

        out_buf.seek(0)
        return zipfile.ZipFile(out_buf, "r")

    def extract_to(
        self,
        dest: Union[str, os.PathLike],
        *,
        add_root: bool = False,
        root_name: Optional[str] = None,
    ) -> str:
        """Extract this directory subtree to the filesystem.

        Parameters
        ----------
        dest : str or os.PathLike
            Destination directory where contents will be written.
        add_root : bool, optional
            If True, wrap extracted contents under a top-level folder named
            root_name (or this directory's name when None). If False, contents
            are placed directly under dest, preserving internal structure.
        root_name : Optional[str], optional
            Optional explicit root folder name when add_root is True.

        Returns
        -------
        str
            Absolute path to the extraction root (dest or dest/root_name).
        """
        src_zip = self._resolve_zipobj()
        prefix = self.path.strip("/")
        if prefix:
            prefix += "/"

        dest_path = Path(dest)
        if add_root:
            root = (root_name or (self.name or "root")).strip("/")
            base = dest_path / root
        else:
            base = dest_path

        base_abs = Path(_ensure_parent_dir(base))
        for info in src_zip.infolist():
            fn = info.filename
            if not fn.startswith(prefix):
                continue
            rel = fn[len(prefix):]
            if not rel:
                continue

            target = base_abs / rel
            if fn.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            data = src_zip.read(fn)
            with open(target, "wb") as f:
                f.write(data)
            # best-effort permission preservation
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                try:
                    os.chmod(target, mode)
                except OSError:
                    pass

        return str(base_abs)

    def to_filename(
        self,
        path: Union[str, os.PathLike],
        *,
        compression: int = zipfile.ZIP_DEFLATED,
        include_dir_entries: bool = True,
        add_root: bool = False,
        root_name: Optional[str] = None,
    ) -> str:
        """Persist this directory subtree as a zip file written to path."""
        return zippeddir_to_filename(
            self,
            path,
            compression=compression,
            include_dir_entries=include_dir_entries,
            add_root=add_root,
            root_name=root_name,
        )


# ---------------------------------------------------------------------------
# walk over ZipFile
# ---------------------------------------------------------------------------


def walk(
    zipobj: zipfile.ZipFile,
    top: str = "",
    *,
    sort_entries: bool = True,
) -> Iterable[Tuple[str, List[ZippedDir], List[ZippedFile]]]:
    """Walk through a ZipFile like os.walk, but with ZippedFile entries.

    Parameters
    ----------
    zipobj : zipfile.ZipFile
        Opened ZipFile object.
    top : str, optional
        Start directory inside the archive (default: root). Use archive-style
        paths (for example "repo-abc/dir"). When top does not correspond to an
        explicit directory entry, the function still yields a subtree rooted at
        top, and dirpath values are archive paths under that prefix.
    sort_entries : bool, optional
        When True, sort directory names and file names for deterministic output.
        Set to False for faster traversal when ordering does not matter.

    Yields
    ------
    (dirpath, dirnames, fileentries)
        dirpath : str
            Current archive path ("" for root or, for example, "repo-abc/dir").
        dirnames : List[ZippedDir]
            Sorted list of immediate subdirectories as ZippedDir objects.
        fileentries : List[ZippedFile]
            Sorted list of file entries; each has .open(), .read(), .buffer().
    """
    tree_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"dirs": set(), "files": {}})

    start = top.strip("/")
    prefix = f"{start}/" if start else ""

    def _is_dir(info: zipfile.ZipInfo) -> bool:
        # ZipInfo.is_dir() exists on modern Python, but keep a safe fallback.
        try:
            return info.is_dir()  # type: ignore[attr-defined]
        except Exception:
            return info.filename.endswith("/")

    # Single pass over the archive; restrict to subtree early when top is given.
    for info in zipobj.infolist():
        arcname = info.filename
        norm = arcname.rstrip("/")
        if not norm:
            continue

        # Restrict to the requested subtree if provided.
        if start:
            if norm != start and not norm.startswith(prefix):
                continue

        parts = norm.split("/")
        parent = "/".join(parts[:-1])  # "" at root
        leaf = parts[-1]

        if _is_dir(info):
            tree_map[parent]["dirs"].add(leaf)
        else:
            tree_map[parent]["files"][leaf] = ZippedFile(name=leaf, arcname=norm, zipobj=zipobj)

        # Ensure intermediate directories are known.
        for i in range(len(parts) - 1):
            up_parent = "/".join(parts[:i])
            up_child = parts[i]
            tree_map[up_parent]["dirs"].add(up_child)

    # If the subtree has no entries, return nothing.
    if start and start not in tree_map:
        return

    built_dirs: Dict[str, ZippedDir] = {}

    def _build(path: str) -> ZippedDir:
        if path in built_dirs:
            return built_dirs[path]

        dirset = tree_map[path]["dirs"]
        files_dict = tree_map[path]["files"]

        if sort_entries:
            dirnames = sorted(dirset)
            filekeys = sorted(files_dict.keys())
        else:
            # Sets/dicts are already in-memory; avoid sorting for speed.
            dirnames = list(dirset)
            filekeys = list(files_dict.keys())

        files = [files_dict[k] for k in filekeys]
        subs: List[ZippedDir] = []
        for name in dirnames:
            sub_path = f"{path}/{name}" if path else name
            subs.append(_build(sub_path))

        obj = ZippedDir(
            name=path.rsplit("/", 1)[-1] if path else "",
            path=path,
            dirs=subs,
            files=files,
        )
        built_dirs[path] = obj
        return obj

    def _walk(current_path: str):
        cur_dir = _build(current_path)
        yield current_path, cur_dir.dirs, cur_dir.files
        for sub in cur_dir.dirs:
            yield from _walk(sub.path)

    yield from _walk(start)


# ---------------------------------------------------------------------------
# basic helpers
# ---------------------------------------------------------------------------


def bytes_to_zipfile(zip_bytes: bytes) -> zipfile.ZipFile:
    """Open a zip archive from a bytes object.

    This is a convenience wrapper around zipfile.ZipFile(io.BytesIO(zip_bytes)).

    Parameters
    ----------
    zip_bytes : bytes
        The binary content of a zip archive.

    Returns
    -------
    zipfile.ZipFile
        A readable ZipFile object.
    """
    return zipfile.ZipFile(io.BytesIO(zip_bytes))


# ---------------------------------------------------------------------------
# search helpers
# ---------------------------------------------------------------------------


def fetch_files_in_zip(
    zipobj: zipfile.ZipFile,
    filename: str,
    top: str = "",
    wildcard: bool = True,
    regex: Optional[str] = None,
) -> List[ZippedFile]:
    """Search for files in a ZipFile whose leaf name matches filename.

    Parameters
    ----------
    zipobj : zipfile.ZipFile
        Opened ZipFile object.
    filename : str
        Target filename (exact match or pattern).
    top : str, optional
        Directory prefix to restrict search (default: root).
    wildcard : bool, optional
        If True, use fnmatch (shell-style wildcards) for filename matching.
    regex : str, optional
        If given, use this regex pattern to match filenames (overrides wildcard).

    Returns
    -------
    List[ZippedFile]
        List of matching ZippedFile objects.
    """
    matches: List[ZippedFile] = []
    pattern = re.compile(regex) if regex else None
    for _, _, fileentries in walk(zipobj, top=top):
        for entry in fileentries:
            if pattern is not None:
                if pattern.fullmatch(entry.name):
                    matches.append(entry)
            elif wildcard:
                if fnmatch.fnmatch(entry.name, filename):
                    matches.append(entry)
            else:
                if entry.name == filename:
                    matches.append(entry)
    return matches


def fetch_dirs_in_zip(
    zipobj: zipfile.ZipFile,
    dirname: str,
    top: str = "",
    wildcard: bool = True,
    regex: Optional[str] = None,
    match_scope: str = "basename",   # "basename" | "fullpath"
) -> List[ZippedDir]:
    """Return ZippedDir trees rooted at the matched directories.

    Parameters
    ----------
    zipobj : zipfile.ZipFile
        The opened zip file object.
    dirname : str
        Directory name pattern to match.
    top : str, optional
        The starting directory inside the archive (default: root).
    wildcard : bool, optional
        Whether to allow wildcard matching (default: True).
    regex : Optional[str], optional
        Regex pattern to match directories (default: None).
    match_scope : {"basename", "fullpath"}, optional
        Matching scope:
        - "basename": match only against the final directory name.
        - "fullpath": match against the entire directory path.

    Returns
    -------
    List[ZippedDir]
        A list of matched ZippedDir objects.

    Raises
    ------
    ValueError
        If match_scope is not "basename" or "fullpath".
    """
    if match_scope not in {"basename", "fullpath"}:
        raise ValueError(f"Invalid match_scope: {match_scope!r}")

    index: Dict[str, Tuple[List[ZippedDir], List[ZippedFile]]] = {}
    for dirpath, direntries, fileentries in walk(zipobj, top=top):
        index[dirpath] = (direntries, fileentries)

    def _target(dirpath: str) -> str:
        if match_scope == "basename":
            return dirpath.rsplit("/", 1)[-1] if dirpath else ""
        return dirpath

    def _match(dirpath: str) -> bool:
        target = _target(dirpath)
        if regex is not None:
            return re.search(regex, target) is not None
        if wildcard:
            return fnmatch.fnmatch(target, dirname)
        return target == dirname

    def _build_dir(path: str) -> ZippedDir:
        direntries, files = index.get(path, ([], []))
        subdirs: List[ZippedDir] = []
        for d in direntries:
            subdirs.append(_build_dir(d.path))
        return ZippedDir(
            name=path.rsplit("/", 1)[-1] if path else "",
            path=path,
            dirs=subdirs,
            files=files,
        )

    results: List[ZippedDir] = []
    for dirpath in index.keys():
        if _match(dirpath):
            results.append(_build_dir(dirpath))
    return results


# ---------------------------------------------------------------------------
# low-level copy helpers
# ---------------------------------------------------------------------------


def _copy_zip(
    zipobj: zipfile.ZipFile,
    dst_path: Union[str, os.PathLike],
    compression: int = zipfile.ZIP_DEFLATED,
    include_dir_entries: bool = True,
) -> None:
    """Copy all entries from an existing ZipFile to a new zip at dst_path.

    Re-compresses entries using compression.
    """
    dst_path = _ensure_parent_dir(dst_path)
    with zipfile.ZipFile(dst_path, "w", compression=compression) as out:
        written: Set[str] = set()
        if include_dir_entries:
            dirs = set()
            for info in zipobj.infolist():
                name = info.filename
                if name.endswith("/"):
                    dirs.add(name)
                else:
                    parts = name.split("/")[:-1]
                    cur: List[str] = []
                    for p in parts:
                        cur.append(p)
                        dirs.add("/".join(cur) + "/")
            for d in sorted(dirs):
                di = zipfile.ZipInfo(d)
                di.external_attr = (0o40755 << 16)
                out.writestr(di, b"")
                written.add(d)

        for info in zipobj.infolist():
            name = info.filename
            if name.endswith("/"):
                if include_dir_entries and name not in written:
                    di = zipfile.ZipInfo(name)
                    di.date_time = info.date_time
                    di.external_attr = info.external_attr
                    out.writestr(di, b"")
                    written.add(name)
                continue
            data = zipobj.read(name)
            ni = zipfile.ZipInfo(name)
            ni.date_time = info.date_time
            ni.external_attr = info.external_attr
            out.writestr(ni, data)


# ---------------------------------------------------------------------------
# ZippedFile method implementation
# ---------------------------------------------------------------------------


def zippedfile_to_filename(
    self: ZippedFile,
    path: Union[str, os.PathLike],
    arcname: Optional[str] = None,
) -> str:
    """Extract this single file to disk.

    Behavior:
      - If `path` points to a directory, the file is written under that
        directory using `arcname` (if provided) or the entry name.
      - If `path` points to a file, the file content is written directly to
        that location. When `arcname` is provided, the file name is overridden
        relative to the parent directory of `path`.
    """
    target = os.fspath(path)

    # Decide whether path is a directory target
    is_dir_target = os.path.isdir(target) or target.endswith(os.sep)
    if is_dir_target:
        rel = arcname or self.name
        target = os.path.join(target, rel)
    elif arcname:
        # Override filename relative to the parent of the given path
        parent = os.path.dirname(target) or "."
        target = os.path.join(parent, arcname)

    abs_path = _ensure_parent_dir(target)
    with open(abs_path, "wb") as f:
        f.write(self.read())
    return abs_path


# ---------------------------------------------------------------------------
# ZippedDir method implementation
# ---------------------------------------------------------------------------


def zippeddir_to_filename(
    self: ZippedDir,
    path: Union[str, os.PathLike],
    compression: int = zipfile.ZIP_DEFLATED,
    include_dir_entries: bool = True,
    add_root: bool = False,
    root_name: Optional[str] = None,
) -> str:
    """Save this directory subtree into a new zip file at path.

    Mirrors ZippedDir.isolate() options but writes directly to disk.
    """
    abs_path = _ensure_parent_dir(path)
    src_zip = self._resolve_zipobj()
    prefix = self.path.strip("/")
    if prefix:
        prefix += "/"

    if add_root:
        root = (root_name or (self.name or "root")).strip("/")
        root_prefix = f"{root}/"
    else:
        root_prefix = ""

    with zipfile.ZipFile(abs_path, "w", compression=compression) as out_zip:
        if add_root and include_dir_entries:
            ri = zipfile.ZipInfo(root_prefix)
            ri.external_attr = (0o40755 << 16)
            out_zip.writestr(ri, b"")

        # copy matching entries
        for info in src_zip.infolist():
            fn = info.filename
            if not fn.startswith(prefix):
                continue
            rel = fn[len(prefix):]
            if not rel:
                continue
            arcname = root_prefix + rel

            if arcname.endswith("/"):
                if include_dir_entries:
                    di = zipfile.ZipInfo(arcname)
                    di.date_time = info.date_time
                    di.external_attr = (0o40755 << 16)
                    out_zip.writestr(di, b"")
                continue

            data = src_zip.read(fn)
            ni = zipfile.ZipInfo(arcname)
            ni.date_time = info.date_time
            ni.external_attr = info.external_attr
            out_zip.writestr(ni, data)

        if include_dir_entries:
            written = set(out_zip.namelist())
            need_dirs: Set[str] = set()
            for name in written:
                if name.endswith("/"):
                    continue
                parts = name.split("/")[:-1]
                cur: List[str] = []
                for p in parts:
                    cur.append(p)
                    need_dirs.add("/".join(cur) + "/")
            for d in sorted(need_dirs):
                if d not in written:
                    di = zipfile.ZipInfo(d)
                    di.external_attr = (0o40755 << 16)
                    out_zip.writestr(di, b"")
    return abs_path


# ---------------------------------------------------------------------------
# Generic dispatcher
# ---------------------------------------------------------------------------


def to_filename(
    obj: Union[
        zipfile.ZipFile,
        ZippedDir,
        ZippedFile,
        str,
        bytes,
        bytearray,
        io.BytesIO,
    ],
    path: Union[str, os.PathLike],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    include_dir_entries: bool = True,
    add_root: bool = False,
    root_name: Optional[str] = None,
    arcname: Optional[str] = None,
) -> str:
    """Persist an object to disk.

    Supported:
      - zipfile.ZipFile: copy all entries into a new zip.
      - ZippedDir: save the subtree (same options as ZippedDir.to_filename()).
      - ZippedFile: extract the file to disk (arcname can rename the output).
      - str: encode as utf-8 and write to a raw file.
      - bytes/bytearray: write to a raw file.
      - io.BytesIO: write buffer content to a raw file.

    When obj is a str, bytes, bytearray, or BytesIO, the output filename
    defaults to `path` (overridden by arcname when provided). If `path` is a
    directory, the filename defaults to the basename of `path` without its
    extension, or "payload" when empty.
    """
    abs_path = _ensure_parent_dir(path)

    if isinstance(obj, zipfile.ZipFile):
        _copy_zip(obj, abs_path, compression=compression, include_dir_entries=include_dir_entries)
        return abs_path

    if isinstance(obj, ZippedDir):
        return obj.to_filename(
            abs_path,
            compression=compression,
            include_dir_entries=include_dir_entries,
            add_root=add_root,
            root_name=root_name,
        )

    if isinstance(obj, ZippedFile):
        return zippedfile_to_filename(obj, abs_path, arcname=arcname)

    if isinstance(obj, (str, bytes, bytearray, io.BytesIO)):
        # Determine target file path (not a zip)
        target = abs_path
        if os.path.isdir(abs_path) or str(path).endswith(os.sep):
            default_name = arcname or os.path.basename(abs_path).rsplit(".", 1)[0] or "payload"
            target = os.path.join(abs_path, default_name)
        elif arcname:
            target = os.path.join(os.path.dirname(abs_path) or ".", arcname)
        target = _ensure_parent_dir(target)

        if isinstance(obj, io.BytesIO):
            data = obj.getvalue()
        elif isinstance(obj, str):
            data = obj.encode("utf-8")
        else:
            data = bytes(obj)

        with open(target, "wb") as f:
            f.write(data)
        return target

    raise TypeError(f"Unsupported type for to_filename: {type(obj)!r}")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def load(path: Union[str, os.PathLike]) -> zipfile.ZipFile:
    """Open a zip archive from a file path.

    A convenience wrapper for zipfile.ZipFile(path, "r").

    Parameters
    ----------
    path : str or os.PathLike
        Path to the zip archive file.

    Returns
    -------
    zipfile.ZipFile
        A readable ZipFile object.
    """
    return zipfile.ZipFile(os.fspath(path), "r")


__all__ = [
    "FileBuffer",
    "ZippedFile",
    "ZippedDir",
    "walk",
    "bytes_to_zipfile",
    "create_from_dir",
    "load",
    "fetch_files_in_zip",
    "fetch_dirs_in_zip",
    "to_filename",
]

def __dir__() -> List[str]:
    return sorted(__all__)
