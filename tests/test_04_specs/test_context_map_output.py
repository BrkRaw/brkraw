"""Context map output rules (b1 bundle B5): path template, utils, split, collisions.

Split cases and messages come from the WI-0039 run-4 prototype; template cases
from Lee's wi-0039-lee-3 reference function.
"""
from __future__ import annotations

import numpy as np
import pytest

from brkraw.specs.context_map import ContextMapError
from brkraw.specs.context_map.output import (
    SplitError,
    plan_split,
    render_template,
    resolve_names,
    select_frames,
    validate_split_parts,
)

S = slice(None)


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

T = "sub-{bids.sub}/ses-{bids.ses}[_task-{bids.task}]_{bids.suffix}"


def test_group_removed_when_tag_empty_and_kept_when_present():
    assert render_template(T, {"bids.sub": "01", "bids.ses": "b", "bids.suffix": "T2w"}) == ("sub-01/ses-b_T2w", [])
    v = {"bids.sub": "01", "bids.ses": "b", "bids.task": "rest", "bids.suffix": "bold"}
    assert render_template(T, v) == ("sub-01/ses-b_task-rest_bold", [])


def test_none_empty_lists_and_zero():
    for empty in (None, ""):
        assert render_template(T, {"bids.sub": "01", "bids.ses": "b", "bids.task": empty, "bids.suffix": "x"})[0] == "sub-01/ses-b_x"
    assert render_template("E{a}[_TE{b}]", {"a": 7, "b": [10.0, 20.0]}) == ("E7_TE10.0-20.0", [])
    assert render_template("a[_{x}]", {"x": ["p", None, "", "q"]}) == ("a_p-q", [])
    assert render_template("a[_{x}]", {"x": []}) == ("a", [])
    assert render_template("r[_{x}]", {"x": 0}) == ("r_0", [])
    assert render_template("a[_{x}{y}]", {"x": "1", "y": None}) == ("a", [])


def test_warnings_escapes_and_literals():
    assert render_template("{a}/{b}/{c}", {"b": "B"}) == ("/B/", ["empty tag {a} outside [ ]", "empty tag {c} outside [ ]"])
    assert render_template("x[_{y}]", {}) == ("x", [])
    assert render_template("\\[{x}\\]", {"x": "1"}) == ("[1]", [])
    assert render_template("a[_\\[{x}\\]]", {}) == ("a", [])
    assert render_template("a\\b{x}", {"x": "1"}) == ("a\\b1", [])
    assert render_template("[fixed]", {}) == ("fixed", [])
    assert render_template("{ bids.sub }", {"bids.sub": "01"}) == ("01", [])
    assert render_template("TE{TE (ms)}", {"TE (ms)": 12.5}) == ("TE12.5", [])


@pytest.mark.parametrize("bad", ["a[b[c]]", "a]b", "a[b", "{x", "x}", "{a{b}}", "[{x]}"])
def test_template_errors(bad):
    with pytest.raises(ValueError):
        render_template(bad, {"x": "1", "a": "1", "b": "1"})


def test_utils_values_in_groups():
    tpl = "{lab.animal}/E{lab.scan}[_sp{utils.slicepack}][_part{utils.split}]"
    base = {"lab.animal": "R07", "lab.scan": 8}
    assert render_template(tpl, {**base, "utils.slicepack": None, "utils.split": None}) == ("R07/E8", [])
    assert render_template(tpl, {**base, "utils.slicepack": 2, "utils.split": 1}) == ("R07/E8_sp2_part1", [])


# ---------------------------------------------------------------------------
# Split: axis and frames (numpy rules)
# ---------------------------------------------------------------------------

CASES = [
    ("fmap-echo-int", ["spatial"] * 3 + ["echo"], (2, 2, 2, 2),
     [{"axis": "echo", "frames": 0}, {"axis": "echo", "frames": 1}],
     [(S, S, S, 0), (S, S, S, 1)], []),
    ("fmap-echo-list", ["spatial"] * 3 + ["echo"], (2, 2, 2, 2),
     [{"axis": "echo", "frames": [0]}, {"axis": "echo", "frames": [1]}],
     [(S, S, S, [0]), (S, S, S, [1])], []),
    ("bold-drop-dummy", ["spatial"] * 3 + ["cycle"], (2, 2, 2, 10),
     [{"frames": "5:"}], [(S, S, S, slice(5, None))],
     ["note: frames [0, 1, 2, 3, 4] are in no part (not written)"]),
    ("me-bold-by-echo", ["spatial"] * 3 + ["echo", "cycle"], (2, 2, 2, 3, 4),
     [{"axis": "echo", "frames": i} for i in range(3)], [(S, S, S, i) for i in range(3)], []),
    ("me-bold-by-cycle", ["spatial"] * 3 + ["echo", "cycle"], (2, 2, 2, 3, 4),
     [{"axis": "cycle", "frames": "0:2"}, {"axis": "cycle", "frames": "2:4"}],
     [(S, S, S, S, slice(0, 2)), (S, S, S, S, slice(2, 4))], []),
    ("neg-and-step", ["spatial"] * 3 + ["cycle"], (2, 2, 2, 6),
     [{"frames": [-1, 0]}, {"frames": "::2"}], [(S, S, S, [-1, 0]), (S, S, S, slice(None, None, 2))],
     ["note: frames [0] are in more than one part", "note: frames [1, 3] are in no part (not written)"]),
    ("clamp-warn", ["spatial"] * 3 + ["cycle"], (2, 2, 2, 4),
     [{"frames": "0:100"}], [(S, S, S, slice(0, 100))], ["split: '0:100' reaches past 4 frames; Python clamps it"]),
    ("axis-number", ["spatial"] * 3 + ["cycle", "cycle"], (2, 2, 2, 2, 3),
     [{"axis": 4, "frames": 1}], [(S, S, S, S, 1)], ["note: frames [0, 2] are in no part (not written)"]),
]


@pytest.mark.parametrize("name, desc, shape, parts, literal, notes", CASES, ids=[c[0] for c in CASES])
def test_split_parts_equal_direct_numpy_indexing(name, desc, shape, parts, literal, notes):
    data = np.arange(int(np.prod(shape))).reshape(shape)
    before = data.copy()
    plans, got_notes = plan_split(desc, shape, parts)
    assert got_notes == notes
    for plan, index in zip(plans, literal):
        out, _ = select_frames(data, desc, parts[plan["part"] - 1].get("axis"), parts[plan["part"] - 1]["frames"])
        assert np.array_equal(out, data[index])
    assert np.array_equal(data, before)


ERRORS = [
    (["spatial"] * 3, (2, 2, 2), [{"frames": 0}], "split: this scan has no frame axis"),
    (["spatial"] * 3 + ["echo", "cycle"], (2, 2, 2, 2, 3), [{"frames": 0}], "split: axis required"),
    (["spatial"] * 3 + ["cycle"], (2, 2, 2, 3), [{"axis": "echo", "frames": 0}], "split: no axis 'echo'"),
    (["spatial"] * 3 + ["echo"], (2, 2, 2, 2), [{"axis": "FG_ECHO", "frames": 0}], "split: axis name must be lowercase"),
    (["spatial", "spatial", "slice", "cycle"], (2, 2, 2, 3), [{"axis": "slice", "frames": 0}], "split: 'slice' is a spatial axis"),
    (["spatial"] * 3 + ["cycle", "cycle"], (2, 2, 2, 2, 3), [{"axis": "cycle", "frames": 0}], "split: axis 'cycle' appears 2 times"),
    (["spatial"] * 3 + ["echo", "cycle"], (2, 2, 2, 2, 3), [{"axis": "echo", "frames": 0}, {"axis": "cycle", "frames": 0}],
     "split: all parts of one scan must use the same axis"),
    (["spatial"] * 3 + ["cycle"], (2, 2, 2, 3), [{"frames": 3}], "split: frame 3 out of range"),
    (["spatial"] * 3 + ["cycle"], (2, 2, 2, 3), [{"frames": [0, -4]}], "split: frame -4 out of range"),
    (["spatial"] * 3 + ["cycle"], (2, 2, 2, 3), [{"frames": [0, -3]}], "split: frame repeated"),
    (["spatial"] * 3 + ["cycle"], (2, 2, 2, 3), [{"frames": "5:"}], "split: '5:' selects no frame"),
    (["spatial"] * 3 + ["cycle"], (2, 2, 2, 3), [{"frames": "::0"}], "split: slice step cannot be zero"),
    (["spatial"] * 3 + ["cycle"], (2, 2, 2, 3), [{"frames": "a:b"}], "split: 'a:b' is not start:stop"),
    (["spatial"] * 3 + ["cycle"], (2, 2, 2, 3), [{"axis": "cycle"}], "split: part 1 has no frames"),
]


@pytest.mark.parametrize("desc, shape, parts, message", ERRORS)
def test_split_errors(desc, shape, parts, message):
    with pytest.raises(SplitError) as info:
        plan_split(desc, shape, parts)
    assert str(info.value).startswith(message)
    assert isinstance(info.value, ContextMapError)


def test_split_part_shape_is_checked():
    validate_split_parts([{"axis": "echo", "frames": 0, "bids": {"suffix": "m"}, "sidecar": {"A": 1}}], ["bids"])
    for bad, message in (
        ([], "non-empty list"),
        ([{"axis": "echo"}], "has no frames"),
        ([{"frames": 0, "cycle_index": 0}], "cycle_index"),
        ([{"frames": 0, "other": {"x": 1}}], "other"),
        ([{"frames": 0, "bids": "m"}], "bids"),
    ):
        with pytest.raises(SplitError, match=message):
            validate_split_parts(bad, ["bids"])


# ---------------------------------------------------------------------------
# Collisions (default error, on_collision: suffix)
# ---------------------------------------------------------------------------


def test_collisions_error_and_suffix():
    none = lambda name: False  # noqa: E731
    with pytest.raises(ValueError, match="scan 6 and scan 5 -> x"):
        resolve_names([("scan 5", "x"), ("scan 6", "x")], mode="error", taken=set(), exists=none)
    assert resolve_names([("scan 5", "x"), ("scan 6", "x")], mode="suffix", taken=set(), exists=none) == ["x", "x_2"]
    with pytest.raises(ValueError, match="already exists"):
        resolve_names([("scan 5", "x")], mode="error", taken=set(), exists=lambda n: True)
