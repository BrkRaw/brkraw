"""brkraw.core.cache: sizes per entry and clearing chosen entries only (WI-0074)."""
import os

import pytest

from brkraw.core import cache


def _tree(root):
    (root / "sordino" / "sub").mkdir(parents=True)
    (root / "sordino" / "recon_a.bin").write_bytes(b"x" * 1000)
    (root / "sordino" / "recon_a.bin.json").write_bytes(b"y" * 10)
    (root / "sordino" / "sub" / "t.npy").write_bytes(b"z" * 5)
    (root / "viewer").mkdir()
    (root / "viewer" / "v.npy").write_bytes(b"v" * 200)
    (root / "empty").mkdir()
    (root / "loose.txt").write_bytes(b"l" * 7)
    (root / "loose2.bin").write_bytes(b"m" * 3)
    return root


def test_default_result_is_unchanged(tmp_path):
    root = _tree(tmp_path / "cache")
    info = cache.get_info(path=root)
    assert set(info) == {"path", "size", "count"}
    assert (info["size"], info["count"]) == (1225, 6)


def test_entries_per_subfolder_and_one_for_loose_files(tmp_path):
    root = _tree(tmp_path / "cache")
    info = cache.get_info(path=root, by_entry=True)
    names = [e["name"] for e in info["entries"]]
    assert names == ["empty", "sordino", "viewer", cache.FILES_ENTRY]
    by = {e["name"]: e for e in info["entries"]}
    assert (by["sordino"]["size"], by["sordino"]["count"], by["sordino"]["is_dir"]) == (1015, 3, True)
    assert (by[cache.FILES_ENTRY]["size"], by[cache.FILES_ENTRY]["count"]) == (10, 2)
    assert sum(e["size"] for e in info["entries"]) == info["size"]
    assert cache.get_info(path=tmp_path / "missing", by_entry=True)["entries"] == []


def test_a_link_in_the_cache_adds_no_size(tmp_path):
    root = _tree(tmp_path / "cache")
    big = tmp_path / "outside.bin"
    big.write_bytes(b"o" * 5000)
    os.symlink(big, root / "link.bin")
    by = {e["name"]: e for e in cache.get_info(path=root, by_entry=True)["entries"]}
    assert (by[cache.FILES_ENTRY]["size"], by[cache.FILES_ENTRY]["count"]) == (10, 2)


def test_clear_without_only_clears_everything(tmp_path):
    root = _tree(tmp_path / "cache")
    cache.clear(path=root)
    assert list(root.iterdir()) == []


def test_clear_only_sordino_keeps_the_rest(tmp_path):
    root = _tree(tmp_path / "cache")
    cache.clear(path=root, only=["sordino"])
    assert sorted(p.name for p in root.iterdir()) == ["empty", "loose.txt", "loose2.bin", "viewer"]


def test_clear_only_the_loose_files(tmp_path):
    root = _tree(tmp_path / "cache")
    cache.clear(path=root, only=[cache.FILES_ENTRY])
    assert sorted(p.name for p in root.iterdir()) == ["empty", "sordino", "viewer"]


@pytest.mark.parametrize("bad", ["..", ".", "", "a/b", "/abs", "../cache", "nothere", "loose.txt"])
def test_bad_or_unknown_names_delete_nothing(tmp_path, bad):
    root = _tree(tmp_path / "cache")
    (tmp_path / "keep.txt").write_bytes(b"k")
    with pytest.raises(ValueError):
        cache.clear(path=root, only=["viewer", bad])
    assert (root / "viewer" / "v.npy").exists() and (tmp_path / "keep.txt").exists()


def test_a_folder_link_is_removed_as_a_link_only(tmp_path):
    root = _tree(tmp_path / "cache")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"k")
    os.symlink(outside, root / "linked")
    with pytest.raises(ValueError):
        cache.clear(path=root, only=["linked"])        # not a cache subfolder
    cache.clear(path=root, only=[cache.FILES_ENTRY])
    assert not os.path.lexists(root / "linked") and (outside / "keep.txt").exists()
