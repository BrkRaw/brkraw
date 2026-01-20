import io
import os
import zipfile
from pathlib import Path

import pytest

from tests.helpers import prep_module

# Load the zip module using your helper
p = prep_module("core", "zip")

FileBuffer = p.FileBuffer
ZippedFile = p.ZippedFile
ZippedDir = p.ZippedDir


# ---------------------------------------------------------------------------
# helpers for tests
# ---------------------------------------------------------------------------


def _build_sample_tree(tmp_path: Path) -> Path:
    """Create a small directory tree and return its root path.

    Layout:
        root/
          README.md
          data/
            config.json
          pkg/
            __init__.py
            module.py
    """
    root = tmp_path / "sample_root"
    (root / "data").mkdir(parents=True)
    (root / "pkg").mkdir(parents=True)

    (root / "README.md").write_text("root readme", encoding="utf-8")
    (root / "data" / "config.json").write_text('{"x": 1}', encoding="utf-8")
    (root / "pkg" / "__init__.py").write_text("# init", encoding="utf-8")
    (root / "pkg" / "module.py").write_text("print('hello')", encoding="utf-8")

    return root


def _build_sample_zip_from_dir(tmp_path: Path) -> Path:
    """Create a sample zip file on disk using create_from_dir."""
    src_root = _build_sample_tree(tmp_path)
    zip_path = tmp_path / "sample.zip"
    p.create_from_dir(zip_path, src_root)
    return zip_path


# ---------------------------------------------------------------------------
# FileBuffer tests
# ---------------------------------------------------------------------------


def test_filebuffer_bytes_and_to_filename(tmp_path: Path):
    """FileBuffer should preserve content and write correctly to disk."""
    data = b"hello zip"
    buf = io.BytesIO(data)
    fb = FileBuffer(name="test.bin", buffer=buf)

    # bytes() should return full content without changing the position
    assert fb.bytes() == data
    assert buf.tell() == 0

    out_path = tmp_path / "out" / "file.bin"
    written = fb.to_filename(out_path)
    assert os.path.isfile(written)

    on_disk = Path(written).read_bytes()
    assert on_disk == data


# ---------------------------------------------------------------------------
# bytes_to_zipfile and walk
# ---------------------------------------------------------------------------


def test_bytes_to_zipfile_and_walk_basic():
    """bytes_to_zipfile and walk should iterate over archive structure correctly."""
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w") as zf:
        zf.writestr("a.txt", b"A")
        zf.writestr("dir/b.txt", b"B")

    zf = p.bytes_to_zipfile(mem.getvalue())

    entries = list(p.walk(zf))
    # Expect at least root and "dir"
    dirpaths = {d for d, _, _ in entries}
    assert "" in dirpaths
    assert "dir" in dirpaths

    # Root should have a.txt
    root = [triple for triple in entries if triple[0] == ""][0]
    root_files = [f.name for f in root[2]]
    assert "a.txt" in root_files

    # "dir" should have b.txt
    sub = [triple for triple in entries if triple[0] == "dir"][0]
    sub_files = [f.name for f in sub[2]]
    assert "b.txt" in sub_files


def test_walk_with_top_prefix(tmp_path: Path):
    """walk(top=...) should start from the given prefix only."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    all_entries = list(p.walk(zf))
    # Walk only under "pkg"
    pkg_entries = list(p.walk(zf, top="pkg"))

    all_dirs = {d for d, _, _ in all_entries}
    pkg_dirs = {d for d, _, _ in pkg_entries}

    assert "pkg" in all_dirs
    # When top is "pkg", dirpath "pkg" should appear as root of this traversal
    assert "pkg" in pkg_dirs
    # Under that, there should be one nested path "pkg/__init__.py" etc.


# ---------------------------------------------------------------------------
# create_from_dir and load
# ---------------------------------------------------------------------------


def test_create_from_dir_and_load(tmp_path: Path):
    """create_from_dir should zip the full directory tree that load then can read."""
    src_root = _build_sample_tree(tmp_path)
    zip_path = tmp_path / "tree.zip"

    created = p.create_from_dir(zip_path, src_root)
    assert os.path.isfile(created)

    zf = p.load(created)
    names = set(zf.namelist())

    # Directory entries may or may not exist, but these files must
    assert "README.md" in names
    assert "data/config.json" in names
    assert "pkg/__init__.py" in names
    assert "pkg/module.py" in names


# ---------------------------------------------------------------------------
# fetch_files_in_zip
# ---------------------------------------------------------------------------


def test_fetch_files_in_zip_exact_and_wildcard(tmp_path: Path):
    """fetch_files_in_zip should support exact and wildcard matching."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    # exact match
    exact = p.fetch_files_in_zip(zf, "README.md", wildcard=False)
    assert len(exact) == 1
    assert exact[0].name == "README.md"

    # wildcard
    py_files = p.fetch_files_in_zip(zf, "*.py", wildcard=True)
    names = sorted(f.name for f in py_files)
    assert names == ["__init__.py", "module.py"]


def test_fetch_files_in_zip_regex(tmp_path: Path):
    """fetch_files_in_zip should support regex matching when regex is provided."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    # match any name ending in ".json" by regex
    matches = p.fetch_files_in_zip(zf, filename="", regex=r".*\.json")
    assert len(matches) == 1
    assert matches[0].name == "config.json"


# ---------------------------------------------------------------------------
# fetch_dirs_in_zip
# ---------------------------------------------------------------------------


def test_fetch_dirs_in_zip_basename_and_fullpath(tmp_path: Path):
    """fetch_dirs_in_zip should match by basename or fullpath depending on match_scope."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    # basename match for "pkg"
    dirs_basename = p.fetch_dirs_in_zip(zf, "pkg", match_scope="basename")
    assert any(d.name == "pkg" for d in dirs_basename)

    # fullpath match for "pkg"
    dirs_fullpath = p.fetch_dirs_in_zip(zf, "pkg", match_scope="fullpath", wildcard=True)
    paths = [d.path for d in dirs_fullpath]
    assert "pkg" in paths


def test_fetch_dirs_in_zip_regex(tmp_path: Path):
    """fetch_dirs_in_zip should support regex matches for directory names."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    dirs = p.fetch_dirs_in_zip(zf, dirname="", regex=r"^p.*", match_scope="basename")
    names = [d.name for d in dirs]
    assert "pkg" in names


def test_fetch_dirs_in_zip_invalid_scope_raises(tmp_path: Path):
    """fetch_dirs_in_zip should raise ValueError for invalid match_scope."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    with pytest.raises(ValueError):
        p.fetch_dirs_in_zip(zf, dirname="pkg", match_scope="invalid-scope")


# ---------------------------------------------------------------------------
# ZippedFile tests
# ---------------------------------------------------------------------------


def test_zippedfile_read_buffer_isolate_and_to_filename(tmp_path: Path):
    """ZippedFile should provide read, buffer, isolate, and extract_to utilities."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    # pick README.md at root
    root_entries = [triple for triple in p.walk(zf) if triple[0] == ""][0]
    readme_entry = [f for f in root_entries[2] if f.name == "README.md"][0]

    content = readme_entry.read()
    assert b"root readme" in content

    buf = readme_entry.buffer()
    assert isinstance(buf, io.BytesIO)
    assert buf.getvalue() == content

    fb = readme_entry.isolate()
    assert isinstance(fb, FileBuffer)
    assert fb.bytes() == content

    out_file = tmp_path / "docs" / "README.md"
    written = readme_entry.extract_to(out_file)
    assert os.path.isfile(out_file)
    assert out_file.read_bytes() == content
    assert written == str(out_file)


# ---------------------------------------------------------------------------
# ZippedDir tests
# ---------------------------------------------------------------------------


def test_zippeddir_isolate_and_to_filename(tmp_path: Path):
    """ZippedDir.isolate and .to_filename should produce a subtree zip."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    pkg_dirs = p.fetch_dirs_in_zip(zf, "pkg", match_scope="basename")
    assert pkg_dirs, "Expected to find pkg directory"
    pkg_dir = pkg_dirs[0]

    # in-memory isolate with root folder
    sub_zip = pkg_dir.isolate(add_root=True, root_name="pkg-root")
    names = set(sub_zip.namelist())
    assert "pkg-root/__init__.py" in names
    assert "pkg-root/module.py" in names

    # on-disk isolate via to_filename
    out_zip = tmp_path / "pkg_subtree.zip"
    written = pkg_dir.to_filename(out_zip, add_root=False)
    assert os.path.isfile(written)

    with zipfile.ZipFile(written, "r") as z:
        z_names = set(z.namelist())
        # no extra root folder when add_root=False
        assert "__init__.py" in z_names or "pkg/__init__.py" in z_names


def test_zippeddir_listdir(tmp_path: Path):
    """ZippedDir.listdir/iterdir should return children in dir->file order."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    pkg_dirs = p.fetch_dirs_in_zip(zf, "pkg", match_scope="basename")
    pkg_dir = pkg_dirs[0]

    names = pkg_dir.listdir()
    assert names == ["__init__.py", "module.py"]

    objs = list(pkg_dir.iterdir())
    assert all(not o.is_dir() for o in objs)
    assert [o.name for o in objs] == ["__init__.py", "module.py"]


def test_zippeddir_extract_to(tmp_path: Path):
    """ZippedDir.extract_to should unpack the subtree with or without root wrapping."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    pkg_dirs = p.fetch_dirs_in_zip(zf, "pkg", match_scope="basename")
    assert pkg_dirs, "Expected to find pkg directory"
    pkg_dir = pkg_dirs[0]

    # With add_root
    dest_root = tmp_path / "out"
    extracted = pkg_dir.extract_to(dest_root, add_root=True, root_name="pkg-root")
    expected_root = dest_root / "pkg-root"
    assert extracted == str(expected_root)
    assert (expected_root / "__init__.py").is_file()
    assert (expected_root / "module.py").is_file()

    # Without add_root
    dest_root2 = tmp_path / "out2"
    extracted2 = pkg_dir.extract_to(dest_root2, add_root=False)
    assert extracted2 == str(dest_root2)
    assert (dest_root2 / "__init__.py").is_file()
    assert (dest_root2 / "module.py").is_file()


# ---------------------------------------------------------------------------
# dispatcher to_filename tests
# ---------------------------------------------------------------------------


def test_to_filename_with_zipfile_copy(tmp_path: Path):
    """to_filename should copy an existing ZipFile correctly."""
    orig_zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(orig_zip_path)

    out_zip_path = tmp_path / "copied.zip"
    written = p.to_filename(zf, out_zip_path)
    assert os.path.isfile(written)

    with zipfile.ZipFile(written, "r") as z:
        orig_names = set(zf.namelist())
        copied_names = set(z.namelist())
        assert orig_names == copied_names


def test_to_filename_with_zippeddir_and_zippedfile(tmp_path: Path):
    """to_filename should handle ZippedDir and extract a ZippedFile."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    # ZippedDir
    pkg_dirs = p.fetch_dirs_in_zip(zf, "pkg", match_scope="basename")
    pkg_dir = pkg_dirs[0]

    out_dir_zip = tmp_path / "pkg_only.zip"
    written_dir = p.to_filename(pkg_dir, out_dir_zip, add_root=True, root_name="src-pkg")
    assert os.path.isfile(written_dir)

    with zipfile.ZipFile(written_dir, "r") as z:
        names = set(z.namelist())
        assert "src-pkg/__init__.py" in names
        assert "src-pkg/module.py" in names

    # ZippedFile extraction
    root_entries = [triple for triple in p.walk(zf) if triple[0] == ""][0]
    readme_entry = [f for f in root_entries[2] if f.name == "README.md"][0]

    out_file = tmp_path / "docs" / "README.txt"
    written_file = p.to_filename(readme_entry, out_file, arcname="README.txt")
    assert os.path.isfile(written_file)
    assert out_file.read_text() == "root readme"


def test_to_filename_with_raw_data_variants(tmp_path: Path):
    """to_filename should accept str, bytes, bytearray, and BytesIO."""
    # str input
    out_str = tmp_path / "str_payload.txt"
    written_str = p.to_filename("hello", out_str)
    assert Path(written_str).read_bytes() == b"hello"

    # bytes input with custom arcname overriding filename
    out_bytes_path = tmp_path / "bytes_payload.bin"
    written_bytes = p.to_filename(b"data", out_bytes_path, arcname="data.bin")
    assert Path(written_bytes).name == "data.bin"
    assert Path(written_bytes).read_bytes() == b"data"

    # BytesIO input
    buf = io.BytesIO(b"buffer-data")
    out_buf = tmp_path / "buf_payload.bin"
    written_buf = p.to_filename(buf, out_buf, arcname="buf.txt")
    assert Path(written_buf).name == "buf.txt"
    assert Path(written_buf).read_bytes() == b"buffer-data"


def test_to_filename_unsupported_type_raises(tmp_path: Path):
    """to_filename should raise TypeError for unsupported object types."""
    class Dummy:
        pass

    dummy = Dummy()
    out_zip = tmp_path / "dummy.zip"

    with pytest.raises(TypeError):
        p.to_filename(dummy, out_zip)


# ---------------------------------------------------------------------------
# smoke test
# ---------------------------------------------------------------------------


def test_zip_module_smoke(tmp_path: Path):
    """Smoke test that exercises the main public API without detailed assertions."""
    zip_path = _build_sample_zip_from_dir(tmp_path)
    zf = p.load(zip_path)

    # Walk the archive
    for dirpath, dirnames, files in p.walk(zf):
        _ = dirpath
        _ = dirnames
        for f in files:
            _ = f.read()

    # Fetch files and dirs
    _ = p.fetch_files_in_zip(zf, "*.py")
    _ = p.fetch_dirs_in_zip(zf, "pkg", match_scope="basename")

    # Isolate a directory if present
    dirs = p.fetch_dirs_in_zip(zf, "pkg", match_scope="basename")
    if dirs:
        sub = dirs[0]
        _ = sub.isolate()
        out_zip = tmp_path / "smoke_pkg.zip"
        p.to_filename(sub, out_zip)

    # Dispatcher with the original zipfile
    out_copy = tmp_path / "smoke_copy.zip"
    p.to_filename(zf, out_copy)

    assert out_copy.is_file()
