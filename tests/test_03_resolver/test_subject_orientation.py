"""Subject pose <-> subject RAS+ for all 16 Biped/Quadruped poses.

Synthetic affines only; no image data. The tests call
``unwrap_to_scanner_xyz`` and ``wrap_to_subject_ras`` directly.
``POSE_TABLE`` is the same table as the comment above ``_PoseStep`` in
``brkraw/resolver/affine.py``; ``test_comment_table_matches`` keeps the two
identical.
"""
from __future__ import annotations

import inspect
from typing import Dict, List, Tuple

import numpy as np
import pytest

from brkraw.apps.loader import helper as loader_helper
from brkraw.resolver import affine as affine_mod
from brkraw.resolver.affine import (
    _apply_pose_step,
    _subject_ras_steps,
    unwrap_to_scanner_xyz,
    wrap_to_subject_ras,
)

# (subject type, pose, labels of scanner +x/+y/+z, [(step, labels after step), ...])
POSE_TABLE = [
    # Biped Head_Supine
    ("Biped", "Head_Supine", "LAS", [("flip_x", "RAS")]),
    # Biped Head_Prone
    ("Biped", "Head_Prone", "RPS", [("roll Rz+180", "LAS"), ("flip_x", "RAS")]),
    # Biped Head_Left
    ("Biped", "Head_Left", "ARS", [("roll Rz+90", "LAS"), ("flip_x", "RAS")]),
    # Biped Head_Right
    ("Biped", "Head_Right", "PLS", [("roll Rz-90", "LAS"), ("flip_x", "RAS")]),
    # Biped Foot_Supine
    ("Biped", "Foot_Supine", "RAI", [("foot Ry+180", "LAS"), ("flip_x", "RAS")]),
    # Biped Foot_Prone
    ("Biped", "Foot_Prone", "LPI", [("foot Ry+180", "RPS"), ("roll Rz+180", "LAS"), ("flip_x", "RAS")]),
    # Biped Foot_Left
    ("Biped", "Foot_Left", "PRI", [("foot Ry+180", "ARS"), ("roll Rz+90", "LAS"), ("flip_x", "RAS")]),
    # Biped Foot_Right
    ("Biped", "Foot_Right", "ALI", [("foot Ry+180", "PLS"), ("roll Rz-90", "LAS"), ("flip_x", "RAS")]),
    # Quadruped Head_Supine
    ("Quadruped", "Head_Supine", "LIA", [("flip_x", "RIA"), ("stand Rx-90", "RAS")]),
    # Quadruped Head_Prone
    ("Quadruped", "Head_Prone", "RSA", [("roll Rz+180", "LIA"), ("flip_x", "RIA"), ("stand Rx-90", "RAS")]),
    # Quadruped Head_Left
    ("Quadruped", "Head_Left", "IRA", [("roll Rz+90", "LIA"), ("flip_x", "RIA"), ("stand Rx-90", "RAS")]),
    # Quadruped Head_Right
    ("Quadruped", "Head_Right", "SLA", [("roll Rz-90", "LIA"), ("flip_x", "RIA"), ("stand Rx-90", "RAS")]),
    # Quadruped Foot_Supine
    ("Quadruped", "Foot_Supine", "RIP", [("foot Ry+180", "LIA"), ("flip_x", "RIA"), ("stand Rx-90", "RAS")]),
    # Quadruped Foot_Prone
    ("Quadruped", "Foot_Prone", "LSP", [("foot Ry+180", "RSA"), ("roll Rz+180", "LIA"), ("flip_x", "RIA"), ("stand Rx-90", "RAS")]),
    # Quadruped Foot_Left
    ("Quadruped", "Foot_Left", "SRP", [("foot Ry+180", "IRA"), ("roll Rz+90", "LIA"), ("flip_x", "RIA"), ("stand Rx-90", "RAS")]),
    # Quadruped Foot_Right
    ("Quadruped", "Foot_Right", "ILP", [("foot Ry+180", "SLA"), ("roll Rz-90", "LIA"), ("flip_x", "RIA"), ("stand Rx-90", "RAS")]),
]

# Stored ParaVision frame assumed by the source comments (labels of stored +x/+y/+z).
RAW_FRAME = {"Biped": "LPS", "Quadruped": "LSA"}

IDS = [f"{t}-{p}" for t, p, _, _ in POSE_TABLE]

# --- independent label helpers (test-side, integer maths) -------------------
_LETTER = {"R": (0, 1), "L": (0, -1), "A": (1, 1), "P": (1, -1), "S": (2, 1), "I": (2, -1)}
_NAMES = (("L", "R"), ("P", "A"), ("I", "S"))


def labels_to_matrix(labels: str) -> np.ndarray:
    mat = np.zeros((3, 3))
    for col, letter in enumerate(labels):
        row, sign = _LETTER[letter]
        mat[row, col] = sign
    return mat


def matrix_to_labels(mat: np.ndarray) -> str:
    out = ""
    for col in range(3):
        rows = [r for r in range(3) if round(mat[r, col]) != 0]
        assert len(rows) == 1, mat
        out += _NAMES[rows[0]][1 if mat[rows[0], col] > 0 else 0]
    return out


def step_matrix(axis: str, degrees) -> np.ndarray:
    if degrees is None:
        mat = np.eye(3)
        mat["xyz".index(axis), "xyz".index(axis)] = -1
        return mat
    c = int(round(np.cos(np.radians(degrees))))
    s = int(round(np.sin(np.radians(degrees))))
    return {
        "x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
        "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
        "z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]),
    }[axis].astype(float)


def step_text(step) -> str:
    if step.degrees is None:
        return f"{step.name}_{step.axis}"
    return f"{step.name} R{step.axis}{step.degrees:+d}"


def labels_from_pose_words(subject_type: str, pose: str) -> str:
    """Oracle from the pose words only (not from the code).

    Physical frame Q = (operator's right, up, toward the operator) is
    right-handed; scanner +x, +y, +z are (1,0,0), (0,1,0), (0,0,-1) in Q.
    A real body obeys R x A = S in Q.
    """
    head_or_foot, gravity = pose.split("_")
    far = np.array([0, 0, -1])
    up = np.array([0, 1, 0])
    anat: Dict[str, np.ndarray] = {}
    head = far if head_or_foot == "Head" else -far
    if subject_type == "Biped":
        anat["S"] = head                      # head end is superior
        on_bed = {"Supine": "P", "Prone": "A", "Left": "L", "Right": "R"}[gravity]
    else:
        anat["A"] = head                      # nose end is anterior
        on_bed = {"Supine": "S", "Prone": "I", "Left": "L", "Right": "R"}[gravity]
    opposite = {"P": "A", "A": "P", "S": "I", "I": "S", "L": "R", "R": "L"}
    positive = opposite[on_bed] if on_bed in ("P", "I", "L") else on_bed
    anat[positive] = up if positive != on_bed else -up
    if "R" not in anat:
        anat["R"] = np.cross(anat["A"], anat["S"])
    elif "A" not in anat:
        anat["A"] = np.cross(anat["S"], anat["R"])
    else:
        anat["S"] = np.cross(anat["R"], anat["A"])
    scanner_axes = [np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, -1])]
    mat = np.array([[axis @ anat[k] for axis in scanner_axes] for k in "RAS"], dtype=float)
    return matrix_to_labels(mat)


def synthetic_affine(seed: int) -> np.ndarray:
    """Oblique, anisotropic voxel affine with a translation (synthetic)."""
    rng = np.random.default_rng(seed)
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    affine = np.eye(4)
    affine[:3, :3] = q @ np.diag([0.1, 0.12, 0.5])
    affine[:3, 3] = rng.normal(scale=20.0, size=3)
    return affine


def as4(mat3: np.ndarray) -> np.ndarray:
    out = np.eye(4)
    out[:3, :3] = mat3
    return out


# --- tests ------------------------------------------------------------------
def test_table_covers_all_16_poses() -> None:
    keys = {(t, p) for t, p, _, _ in POSE_TABLE}
    poses = [f"{h}_{g}" for h in ("Head", "Foot") for g in ("Supine", "Prone", "Left", "Right")]
    assert keys == {(t, p) for t in ("Biped", "Quadruped") for p in poses}
    assert len(POSE_TABLE) == 16


@pytest.mark.parametrize("subject_type,pose,start,walk", POSE_TABLE, ids=IDS)
def test_start_labels_follow_pose_words(subject_type, pose, start, walk) -> None:
    assert labels_from_pose_words(subject_type, pose) == start


@pytest.mark.parametrize("subject_type,pose,start,walk", POSE_TABLE, ids=IDS)
def test_steps_and_labels_after_each_step(subject_type, pose, start, walk) -> None:
    """Run the real step executor, _apply_pose_step, one step at a time.

    Each step must equal the independent test-side matrix (on an oblique affine
    with a translation) and undo itself with ``inverse=True``. The labels after
    each step come from the product of the steps the executor has applied so
    far: start labels times the inverse of that product.
    """
    start_frame = labels_to_matrix(start)
    applied = np.eye(4)                      # steps so far, applied by the code
    affine = synthetic_affine(seed=17)
    got: List[Tuple[str, str]] = []
    for step in _subject_ras_steps(subject_type, pose):
        stepped = _apply_pose_step(affine, step)
        assert np.allclose(stepped, as4(step_matrix(step.axis, step.degrees)) @ affine, atol=1e-9)
        assert np.allclose(_apply_pose_step(stepped, step, inverse=True), affine, atol=1e-9)
        affine = stepped
        applied = _apply_pose_step(applied, step)
        got.append((step_text(step), matrix_to_labels(start_frame @ np.linalg.inv(applied[:3, :3]))))
    assert got == walk
    assert got[-1][1] == "RAS"


@pytest.mark.parametrize("subject_type,pose,start,walk", POSE_TABLE, ids=IDS)
def test_wrap_matrix_matches_table(subject_type, pose, start, walk) -> None:
    expected = labels_to_matrix(start)
    wrapped = wrap_to_subject_ras(np.eye(4), subject_type, pose)
    assert np.allclose(wrapped[:3, :3], expected, atol=1e-12)
    assert np.allclose(wrapped[:3, 3], 0.0, atol=1e-12)
    affine = synthetic_affine(seed=len(pose) + len(subject_type))
    assert np.allclose(wrap_to_subject_ras(affine, subject_type, pose), as4(expected) @ affine, atol=1e-9)


@pytest.mark.parametrize("subject_type,pose,start,walk", POSE_TABLE, ids=IDS)
def test_unwrap_then_wrap_gives_raw_frame_in_ras(subject_type, pose, start, walk) -> None:
    raw_to_ras = as4(labels_to_matrix(RAW_FRAME[subject_type]))
    affine = synthetic_affine(seed=7)
    round_trip = wrap_to_subject_ras(unwrap_to_scanner_xyz(affine, subject_type, pose), subject_type, pose)
    assert np.allclose(round_trip, raw_to_ras @ affine, atol=1e-9)


@pytest.mark.parametrize("subject_type,pose,start,walk", POSE_TABLE, ids=IDS)
def test_wrap_then_unwrap_returns_scanner_affine(subject_type, pose, start, walk) -> None:
    ras_to_raw = as4(labels_to_matrix(RAW_FRAME[subject_type]).T)
    scanner = synthetic_affine(seed=11)
    back = unwrap_to_scanner_xyz(ras_to_raw @ wrap_to_subject_ras(scanner, subject_type, pose), subject_type, pose)
    assert np.allclose(back, scanner, atol=1e-9)


@pytest.mark.parametrize("subject_type,pose,start,walk", POSE_TABLE, ids=IDS)
def test_comment_table_matches(subject_type, pose, start, walk) -> None:
    line = f"#   {subject_type:<9} {pose:<12} {start}  " + "  ".join(f"{s} -> {lab}" for s, lab in walk)
    assert line in inspect.getsource(affine_mod)


@pytest.mark.parametrize("subject_type", ["Phantom", "Other", "OtherAnimal"])
def test_other_types_use_only_the_foot_turn(subject_type) -> None:
    affine = synthetic_affine(seed=3)
    turn = as4(step_matrix("y", 180))
    for pose in ("Head_Supine", "Head_Left"):
        assert np.allclose(wrap_to_subject_ras(affine, subject_type, pose), affine)
        assert np.allclose(unwrap_to_scanner_xyz(affine, subject_type, pose), affine)
    for pose in ("Foot_Supine", "Foot_Right"):
        assert np.allclose(wrap_to_subject_ras(affine, subject_type, pose), turn @ affine)
        assert np.allclose(unwrap_to_scanner_xyz(affine, subject_type, pose), turn @ affine)


def test_missing_subject_type_is_biped() -> None:
    affine = synthetic_affine(seed=5)
    for pose in ("Head_Left", "Foot_Right"):
        assert np.allclose(wrap_to_subject_ras(affine, None, pose), wrap_to_subject_ras(affine, "Biped", pose))
        assert np.allclose(unwrap_to_scanner_xyz(affine, None, pose), unwrap_to_scanner_xyz(affine, "Biped", pose))


# --- override path of get_affine (helper.py) is unchanged --------------------
class _FakeReco:
    def __init__(self, visu_pars) -> None:
        self.visu_pars = True
        self.file_visu_pars = visu_pars
        self._cache: Dict[str, object] = {}

    def _full_path(self, basename: str) -> str:
        return basename


class _FakeScan:
    def __init__(self, affine: np.ndarray, subject_type: str, pose: str) -> None:
        visu = {"VisuSubjectType": subject_type, "VisuSubjectPosition": pose}
        self.avail = {1: _FakeReco(visu)}
        self.affine_info = {1: {"num_slice_packs": 1, "affines": [affine]}}


def test_get_affine_override_is_used_for_wrap_only() -> None:
    raw = synthetic_affine(seed=13)
    scan = _FakeScan(raw, "Biped", "Head_Supine")
    scanner = unwrap_to_scanner_xyz(raw, "Biped", "Head_Supine")

    # No override: metadata type/pose for both unwrap and wrap.
    got = loader_helper.get_affine(scan, space="subject_ras")
    assert np.allclose(got, wrap_to_subject_ras(scanner, "Biped", "Head_Supine"))

    # Override pose/type: unwrap still uses the metadata, wrap uses the override.
    got = loader_helper.get_affine(scan, space="subject_ras", override_subject_pose="Head_Left")
    assert np.allclose(got, wrap_to_subject_ras(scanner, "Biped", "Head_Left"))
    got = loader_helper.get_affine(
        scan, space="subject_ras", override_subject_type="Quadruped", override_subject_pose="Foot_Right"
    )
    assert np.allclose(got, wrap_to_subject_ras(scanner, "Quadruped", "Foot_Right"))

    # Scanner space ignores wrap; overrides are refused outside subject_ras.
    assert np.allclose(loader_helper.get_affine(scan, space="scanner"), scanner)
    with pytest.raises(ValueError):
        loader_helper.get_affine(scan, space="scanner", override_subject_pose="Head_Left")
