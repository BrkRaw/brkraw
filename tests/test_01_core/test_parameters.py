import numpy as np
import pytest
from pathlib import Path
from collections import OrderedDict
from tests.helpers import prep_module

# Load the parameters module using your helper
p = prep_module("core", "parameters")
Parameters = p.Parameters


@pytest.fixture
def fake_parsed_data():
    """Return a minimal parsed JCAMP-like structure for testing Parameters."""
    params = OrderedDict(
        [
            # Header-like keys (no leading $)
            (
                "TITLE",
                {
                    "data": [
                        ["Parameter", "List"],
                        ["ParaVision", 360, "V3.1"],
                    ],
                    "shape": (2,),
                },
            ),
            ("JCAMPDX", {"data": 4.24, "shape": None}),
            ("DATATYPE", {"data": ["Parameter", "Values"], "shape": (2,)}),
            (
                "ORIGIN",
                {
                    "data": ["Bruker", "BioSpin", "MRI", "GmbH"],
                    "shape": (4,),
                },
            ),
            ("OWNER", {"data": "shihlab", "shape": None}),

            # Scalar parameter with no shape
            ("$PVM_EchoTime", {"data": 2.3, "shape": None}),

            # Simple numeric array that should become a 1D numpy array
            ("$PVM_Matrix", {"data": [256, 256], "shape": (2,)}),

            # @-repeat encoded parameter, simplified example: @3*(0)
            (
                "$PVM_EncGenSteps2",
                {
                    "data": ["@3*", 0],
                    "shape": (3,),
                },
            ),

            # Parameter handled by format_registry custom function
            (
                "$PVM_FrqWorkOffsetPpm",
                {
                    "data": [0.0] * 8,
                    "shape": (8,),
                },
            ),

            # Broken shape example to exercise tuple fallback path
            (
                "$BROKEN_Shape",
                {
                    "data": [1, 2],
                    "shape": (3,),  # length mismatch on purpose
                },
            ),

            # Symbolic reference list example
            (
                "$PVM_SymbolicRef",
                {
                    "data": ["<PVM_SliceGeoObj>", "<PVM_MapShimVolDescr>"],
                    "shape": (2, 65),
                },
            ),
        ]
    )

    return {
        "params": params,
        "comments": ["dummy comment"],
        "exceptions": [],
    }


@pytest.fixture
def dummy_path(tmp_path: Path) -> Path:
    """Create a dummy path. File content is irrelevant because we patch the parser."""
    pth = tmp_path / "dummy_method.jdx"
    pth.write_text("dummy")
    return pth


def test_header_string_normalization(monkeypatch, fake_parsed_data, dummy_path):
    """Header keys (no leading $) should be converted to human readable strings."""
    def fake_parse_jcamp(path):
        return fake_parsed_data

    # Patch the parser inside the loaded parameters module
    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    params = Parameters(dummy_path)

    # TITLE: nested list -> joined with semicolons between groups
    assert params.header["TITLE"] == "Parameter List; ParaVision 360 V3.1"
    # JCAMPDX: scalar -> string
    assert params.header["JCAMPDX"] == "4.24"
    # DATATYPE: flat list -> space joined
    assert params.header["DATATYPE"] == "Parameter Values"
    # ORIGIN: flat list -> space joined
    assert params.header["ORIGIN"] == "Bruker BioSpin MRI GmbH"
    # OWNER: plain string
    assert params.header["OWNER"] == "shihlab"


def test_scalar_without_shape(monkeypatch, fake_parsed_data, dummy_path):
    """Parameters with shape None should be stored as plain scalars."""
    def fake_parse_jcamp(path):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    params = Parameters(dummy_path)

    assert "PVM_EchoTime" in params.keys()
    assert isinstance(params.PVM_EchoTime, float)
    assert params.PVM_EchoTime == pytest.approx(2.3)


def test_simple_array_param(monkeypatch, fake_parsed_data, dummy_path):
    """Numeric list with 1D shape should become a numpy array."""
    def fake_parse_jcamp(path):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    params = Parameters(dummy_path)

    mat = params.PVM_Matrix
    assert isinstance(mat, np.ndarray)
    assert mat.shape == (2,)
    assert np.all(mat == np.array([256, 256]))


def test_at_repeat_expansion(monkeypatch, fake_parsed_data, dummy_path):
    """@N*(value) encoded arrays should be expanded before reshaping."""
    def fake_parse_jcamp(path):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    params = Parameters(dummy_path)

    steps2 = params.PVM_EncGenSteps2
    # @3*(0) should expand to [0, 0, 0] and reshape to (3,)
    assert isinstance(steps2, np.ndarray)
    assert steps2.shape == (3,)
    assert np.all(steps2 == np.array([0, 0, 0]))


def test_format_registry_override(monkeypatch, fake_parsed_data, dummy_path):
    """format_registry should allow custom conversion for selected parameters."""
    def fake_parse_jcamp(path):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    def pvm_format(value: dict) -> np.ndarray:
        # Custom formatter: always returns an ndarray using the provided shape
        return np.array(value["data"]).reshape(value["shape"])

    format_registry = {
        "PVM_FrqWorkOffsetPpm": pvm_format,
    }

    params = Parameters(dummy_path, format_registry=format_registry)

    arr = params.PVM_FrqWorkOffsetPpm
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (8,)
    assert np.all(arr == np.zeros(8))


def test_broken_shape_falls_back_to_tuple(monkeypatch, fake_parsed_data, dummy_path):
    """If reshape fails but shape is 1D, code should fall back to a Python tuple."""
    def fake_parse_jcamp(path):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    params = Parameters(dummy_path)

    broken = params.BROKEN_Shape
    # For the fake data, data length is 2 but shape is (3,)
    # _is_array returns False and the code falls back to tuple(data)
    assert isinstance(broken, tuple)
    assert broken == (1, 2)


def test_attribute_and_item_access(monkeypatch, fake_parsed_data, dummy_path):
    """Parameters should support both dict-style and attribute-style access."""
    def fake_parse_jcamp(path):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    params = Parameters(dummy_path)

    # Item style
    assert params["PVM_EchoTime"] == pytest.approx(2.3)

    # Attribute style
    assert params.PVM_Matrix.shape == (2,)

    # Setting a new parameter via attribute
    params.NewParam = 123
    assert params["NewParam"] == 123
    assert params.NewParam == 123


def test_symbolic_ref_list_parsed(monkeypatch, fake_parsed_data, dummy_path):
    """Symbolic reference lists should be detected and converted to numpy arrays."""
    def fake_parser(path):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parser)

    params = Parameters(dummy_path)

    ref = params.PVM_SymbolicRef

    # Should be numpy array
    assert isinstance(ref, np.ndarray)

    # Should have correct length (2 items)
    assert ref.shape == (2,)

    # Should preserve content
    assert list(ref) == ["<PVM_SliceGeoObj>", "<PVM_MapShimVolDescr>"]
    

def test_parameter_smoke():
    """Smoke test over all .jdx fixtures using p.run_smoke_test."""

    fixtures_dir = Path(__file__).parent / "fixtures"
    summary = p.run_smoke_test(fixtures_dir)

    assert summary["init_error_files"] == []
    assert summary["exception_files"] == []
    assert summary["raw_value_params"] == []
    assert summary["attr_access_errors"] == []


def test_source_text_and_save_to(monkeypatch, fake_parsed_data, tmp_path):
    """source_text and save_to should round-trip current source bytes."""
    def fake_parse_jcamp(_):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    text = "##TITLE= test\n##$Param1= 1\n"
    params = Parameters(text.encode("utf-8"))

    assert params.source_text() == text

    out_path = tmp_path / "out.jdx"
    params.save_to(out_path)
    assert out_path.read_text() == text


def test_edit_source_updates_text(monkeypatch, fake_parsed_data):
    """edit_source should update underlying source text."""
    def fake_parse_jcamp(_):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    params = Parameters(b"##TITLE= test\n")
    params.edit_source("##TITLE= updated\n", reparse=False)

    assert params.source_text() == "##TITLE= updated\n"


def test_replace_value_updates_blocks(monkeypatch, fake_parsed_data):
    """replace_value(s) should edit or remove JCAMP blocks."""
    def fake_parse_jcamp(_):
        return fake_parsed_data

    monkeypatch.setattr(p, "parse_jcamp", fake_parse_jcamp)

    src = "##TITLE= test\n##$Param1= 1 2 3\n##$Param2=(2)\n4 5\n"
    params = Parameters(src.encode("utf-8"))
    params.replace_values(
        {
            "Param1": "9",
            "Param2": None,
            "Param3": "(2)\n6 7",
        },
        reparse=False,
    )

    text = params.source_text()
    assert "##$Param1= 9\n" in text
    assert "Param2" not in text
    assert "Param3" not in text
