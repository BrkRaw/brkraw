"""
Unified filesystem view for Paravision-like datasets stored as directories or zip
archives.

This module provides `DatasetFS`, a lightweight abstraction that presents the same
API whether the dataset lives on disk or inside a zip file. It handles:
- Anchor detection so zip members can be referenced with stable, anchor-stripped
  relative paths.
- Directory and zip traversal via a zipfile-like `walk` that mirrors `os.walk`.
- Opening files by archive-relative path, yielding file-like objects or concrete
  temp files for consumers that require real paths.
- Repacking subtrees back into zip files with optional root folder control.

`DatasetFS` is intentionally small and side-effect free so it can be reused
outside Paravision-specific contexts.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import io
from pathlib import Path
from typing import IO, Iterable, Literal, Optional, Tuple, List, Union, TYPE_CHECKING

import os
import zipfile
import shutil
from tempfile import TemporaryDirectory
from . import zip as zipcore

if TYPE_CHECKING:
    from .zip import ZippedDir, ZippedFile


@dataclass
class DatasetFile:
    """Filesystem-backed file entry mirroring zip.ZippedFile API."""

    name: str
    path: str  # archive-style path (anchor-aware)
    fs: "DatasetFS"

    def __repr__(self) -> str:
        try:
            full = self.fs.root / self.fs._normalize_relpath(self.path)
            size = full.stat().st_size
        except Exception:
            size = "?"
        return f"DatasetFile(path='{self.path}', size={size})"

    def is_dir(self) -> bool:
        return False

    def is_file(self) -> bool:
        return True

    def open(self) -> IO[bytes]:
        """Open the file for reading in binary mode."""
        return self.fs.open_binary(self.path)

    def read(self) -> bytes:
        with self.open() as f:
            return f.read()

    def buffer(self) -> io.BytesIO:
        buf = io.BytesIO(self.read())
        buf.seek(0)
        return buf

    def isolate(self) -> zipcore.FileBuffer:
        """Return a FileBuffer wrapping this file's content."""
        buf = self.buffer()
        buf.seek(0)
        return zipcore.FileBuffer(name=self.name, buffer=buf)

    def extract_to(self, dest: Path) -> Path:
        """Write this file to a directory or file path."""
        dest_path = Path(dest)
        if dest_path.is_dir() or str(dest_path).endswith(os.sep):
            dest_path = dest_path / self.name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(self.read())
        return dest_path


@dataclass
class DatasetDir:
    """Filesystem-backed directory entry mirroring zip.ZippedDir API."""

    name: str
    path: str  # archive-style path (anchor-aware)
    fs: "DatasetFS"

    def __repr__(self) -> str:
        dirs = [e for e in self.iterdir() if e.is_dir()]
        files = [e for e in self.iterdir() if e.is_file()]
        return f"DatasetDir(path='{self.path}', dirs={len(dirs)}, files={len(files)})"

    def is_dir(self) -> bool:
        return True

    def is_file(self) -> bool:
        return False

    def listdir(self) -> List[str]:
        """List immediate children names (dirs first, then files)."""
        return self.fs.listdir(self.path)

    def iterdir(self) -> Iterable[Union["DatasetDir", "DatasetFile", "ZippedDir", "ZippedFile"]]:
        """Iterate over children as objects (dirs first, then files)."""
        yield from self.fs.iterdir(self.path)


@dataclass
class DatasetFS:
    """Unified view over a dataset rooted in a directory or zipfile.

    Attributes:
        root: Dataset root (directory or zipfile path).
        _mode: Backing mode, either "dir" or "zip".
        _zip: ZipFile handle when `_mode` is "zip", else None.
        _anchor: Optional top-level directory name inside the archive.
    """
    root: Path
    _mode: Literal["dir", "zip"]
    _zip: Optional[zipfile.ZipFile]
    _anchor: str = field(init=False)

    def __post_init__(self) -> None:
        self._anchor = self._detect_anchor()

    @classmethod
    def from_path(cls, path: Union[Path, str]) -> "DatasetFS":
        """Create a DatasetFS from a directory or zip path.

        Args:
            path: Filesystem path pointing to a dataset root.

        Returns:
            DatasetFS bound to the given path.

        Raises:
            ValueError: If the path is neither a directory nor a valid zip file.
        """
        path = Path(path)
        if path.is_dir():
            return cls(root=path, _mode="dir", _zip=None)
        if path.is_file() and zipfile.is_zipfile(path):
            zf = zipcore.load(path)
            return cls(root=path, _mode="zip", _zip=zf)
        raise ValueError(f"Invalid dataset root: {path}")

    # -- helpers
    def _detect_anchor(self) -> str:
        """Infer the top-level archive directory name.

        Returns:
            Anchor name when identifiable, else an empty string.
        """
        if self._mode == "dir":
            return self.root.name

        assert self._zip is not None
        names = [n.strip("/") for n in self._zip.namelist() if n.strip("/")]
        if not names:
            return ""
        first = names[0].split("/")[0]
        for n in names[1:]:
            if not n.startswith(first + "/") and n != first:
                return ""
        return first

    def _normalize_relpath(self, relpath: str) -> str:
        """Remove anchor prefix if present.

        Args:
            relpath: Archive-relative path that may include the anchor.

        Returns:
            Anchor-stripped relative path.
        """
        relpath = relpath.strip("/")
        if not self._anchor:
            return relpath
        if relpath == self._anchor:
            return ""
        prefix = f"{self._anchor}/"
        if relpath.startswith(prefix):
            return relpath[len(prefix):]
        return relpath

    def _ensure_anchor(self, relpath: str) -> str:
        """Add anchor prefix if missing.

        Args:
            relpath: Archive-relative path without guaranteed anchor.

        Returns:
            Path guaranteed to include the anchor when one exists.
        """
        relpath = relpath.strip("/")
        if not self._anchor:
            return relpath
        if relpath == self._anchor or relpath.startswith(f"{self._anchor}/"):
            return relpath
        return f"{self._anchor}/{relpath}" if relpath else self._anchor

    @property
    def anchor(self) -> str:
        return self._anchor

    def strip_anchor(self, relpath: str) -> str:
        """Remove anchor prefix if present."""
        return self._normalize_relpath(relpath)

    def add_anchor(self, relpath: str) -> str:
        """Ensure anchor prefix is present."""
        return self._ensure_anchor(relpath)

    # -- public API
    def walk(
        self,
        top: str = "",
        *,
        as_objects: bool = False,
        sort_entries: bool = True,
    ) -> Iterable[Tuple[str, List, List]]:
        """Yield (dirpath, direntries, fileentries) with archive-style paths.

        Args:
            top: Optional subdirectory to start from (anchor-aware).
            as_objects: When True, return DatasetDir/ZippedDir and
                DatasetFile/ZippedFile entries; otherwise return name strings.
            sort_entries: When True, sort directory and file entries for deterministic output.
                Set to False for faster traversal when ordering does not matter.

        Yields:
            Tuples of `(dirpath, direntries, fileentries)` using posix-style paths.
        """
        norm_top = top.strip("/")
        if self._anchor and norm_top:
            anchored = norm_top == self._anchor or norm_top.startswith(f"{self._anchor}/")
            if not anchored:
                norm_top = f"{self._anchor}/{norm_top}"

        if self._mode == "dir":
            base = self.root
            rel_top = self._normalize_relpath(norm_top)
            start = base / rel_top if rel_top else base
            if not start.exists():
                return

            if not norm_top and self._anchor:
                # mirror zip.walk: expose the anchor as the top-level directory
                if as_objects:
                    yield "", [DatasetDir(name=self._anchor, path=self._anchor, fs=self)], []
                else:
                    yield "", [self._anchor], []

            for dirpath, dirnames, filenames in os.walk(start):
                rel = os.path.relpath(dirpath, base)
                rel = "" if rel == "." else rel.replace(os.sep, "/")
                rel = self._ensure_anchor(rel)
                if sort_entries:
                    dirnames.sort()
                    filenames.sort()

                if as_objects:
                    dir_objs = [
                        DatasetDir(name=d, path=(f"{rel}/{d}".strip("/")), fs=self) for d in dirnames
                    ]
                    file_objs = [
                        DatasetFile(name=f, path=(f"{rel}/{f}".strip("/")), fs=self) for f in filenames
                    ]
                    yield rel, dir_objs, file_objs
                else:
                    yield rel, dirnames, filenames
        else:
            assert self._zip is not None
            for dirpath, direntries, files in zipcore.walk(self._zip, top=norm_top):
                if sort_entries:
                    try:
                        direntries = sorted(direntries, key=lambda d: d.name)
                        files = sorted(files, key=lambda f: f.name)
                    except Exception:
                        # If entries are plain strings or otherwise unsortable, fall back.
                        pass

                if as_objects:
                    yield dirpath, direntries, files
                else:
                    dnames = [d.name for d in direntries]
                    fnames = [f.name for f in files]
                    if sort_entries:
                        dnames.sort()
                        fnames.sort()
                    yield dirpath, dnames, fnames

    def open_binary(self, relpath: str) -> IO[bytes]:
        """Open a file by archive-relative path.

        Args:
            relpath: Path relative to the dataset root (posix separators).

        Returns:
            File-like object in binary mode.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        relpath = self._normalize_relpath(relpath)

        if self._mode == "dir":
            full = self.root / relpath
            return open(full, "rb")
        else:
            assert self._zip is not None
            arcname = self._ensure_anchor(relpath)
            top = os.path.dirname(arcname)
            leaf = os.path.basename(arcname)
            matches = zipcore.fetch_files_in_zip(
                self._zip,
                leaf,
                top=top,
                wildcard=False,
            )
            if not matches:
                raise FileNotFoundError(arcname)
            return matches[0].open()

    def listdir(self, relpath: str = "") -> List[str]:
        """Return entry names under a relative path (dirs first, then files)."""
        relpath = self._normalize_relpath(relpath)
        target = self._ensure_anchor(relpath)

        if self._mode == "dir":
            base_path = self.root / relpath if relpath else self.root
            if not base_path.exists():
                return []

            dirnames: List[str] = []
            filenames: List[str] = []
            for entry in base_path.iterdir():
                if entry.is_dir():
                    dirnames.append(entry.name)
                else:
                    filenames.append(entry.name)
            dirnames.sort()
            filenames.sort()

            return dirnames + filenames

        # zip mode
        assert self._zip is not None
        dirnames: List[str] = []
        filenames: List[str] = []
        dirobjs: List[zipcore.ZippedDir] = []
        fileobjs: List[zipcore.ZippedFile] = []
        for dirpath, direntries, files in zipcore.walk(self._zip, top=target):
            if dirpath != target:
                continue
            dirobjs = sorted(direntries, key=lambda d: d.name)
            fileobjs = sorted(files, key=lambda f: f.name)
            dirnames = [d.name for d in dirobjs]
            filenames = [f.name for f in fileobjs]
            break

        return dirnames + filenames

    def iterdir(
        self,
        relpath: str = "",
    ) -> Iterable[Union["DatasetDir", "DatasetFile", zipcore.ZippedDir, zipcore.ZippedFile]]:
        """Iterate entries under a relative path as objects (dirs first)."""
        relpath = self._normalize_relpath(relpath)
        target = self._ensure_anchor(relpath)

        if self._mode == "dir":
            base_path = self.root / relpath if relpath else self.root
            if not base_path.exists():
                return iter(())

            dir_entries: List[DatasetDir] = []
            file_entries: List[DatasetFile] = []
            for entry in base_path.iterdir():
                name = entry.name
                p = f"{relpath}/{name}".strip("/")
                if entry.is_dir():
                    dir_entries.append(DatasetDir(name=name, path=self._ensure_anchor(p), fs=self))
                else:
                    file_entries.append(DatasetFile(name=name, path=self._ensure_anchor(p), fs=self))
            dir_entries.sort(key=lambda d: d.name)
            file_entries.sort(key=lambda f: f.name)
            return iter([*dir_entries, *file_entries])

        # zip mode
        assert self._zip is not None
        for dirpath, direntries, files in zipcore.walk(self._zip, top=target):
            if dirpath != target:
                continue
            sorted_dirs = sorted(direntries, key=lambda d: d.name)
            sorted_files = sorted(files, key=lambda f: f.name)
            return iter([*sorted_dirs, *sorted_files])
        return iter(())

    def exists(self, relpath: str) -> bool:
        """Check existence of a dataset-relative path."""
        relpath = self._normalize_relpath(relpath)
        if self._mode == "dir":
            return (self.root / relpath).exists()
        else:
            assert self._zip is not None
            try:
                self._zip.getinfo(self._ensure_anchor(relpath))
                return True
            except KeyError:
                return False

    def compress_to(
        self,
        dest: Path,
        *,
        relpath: str = "",
        add_root: bool = True,
        root_name: Optional[str] = None,
    ) -> Path:
        """Persist the whole dataset or a subtree as a zip file.

        Args:
            dest: Destination zip path.
            relpath: Optional subtree to pack relative to the dataset root.
            add_root: Whether to include a top-level root folder in the zip.
            root_name: Optional name for the root folder when `add_root` is True.

        Returns:
            Path to the created zip file.

        Raises:
            FileNotFoundError: When the requested subtree does not exist.
            RuntimeError: When root detection inside a temporary zip fails.
        """
        dest = Path(dest)
        relpath = self._normalize_relpath(relpath)
        root_name = root_name or self.anchor or (Path(relpath).parts[0] if relpath else self.root.name)
        relpath = relpath.strip("/")

        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / root_name
            if relpath:
                extract_into = tmp_root / relpath
            else:
                extract_into = tmp_root

            if self._mode == "dir":
                src_dir = self.root / relpath
                if not src_dir.exists():
                    raise FileNotFoundError(src_dir)
                extract_into.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src_dir, extract_into, dirs_exist_ok=True)
            else:
                assert self._zip is not None
                arcdir = self._ensure_anchor(relpath)
                if not relpath or arcdir == self.anchor:
                    # whole zip; just copy
                    shutil.copyfile(self.root, dest)
                    return dest

                dirs = zipcore.fetch_dirs_in_zip(
                    self._zip,
                    dirname=arcdir,
                    match_scope="fullpath",
                    wildcard=False,
                )
                target = dirs[0] if dirs else None
                if target is None:
                    raise FileNotFoundError(arcdir)
                with target.isolate() as subzip:
                    extract_into.parent.mkdir(parents=True, exist_ok=True)
                    subzip.extractall(extract_into)

            if add_root:
                tmp_zip = dest.with_suffix(".tmp.zip")
                zipcore.create_from_dir(tmp_zip, tmp_root)
                try:
                    with zipcore.load(tmp_zip) as zf:
                        roots = zipcore.fetch_dirs_in_zip(
                            zf, dirname="", match_scope="fullpath", wildcard=True
                        )
                        root_dir = roots[0] if roots else None
                        if root_dir is None:
                            raise RuntimeError("Failed to locate root dir while zipping.")
                        root_dir.to_filename(
                            dest,
                            add_root=True,
                            root_name=root_name,
                            include_dir_entries=True,
                        )
                finally:
                    Path(tmp_zip).unlink(missing_ok=True)
            else:
                pack_dir = extract_into if relpath else tmp_root
                zipcore.create_from_dir(dest, pack_dir)

            return dest


__all__ = [
    "DatasetFS",
    "DatasetDir",
    "DatasetFile",
]

def __dir__() -> List[str]:
    return sorted(__all__)
