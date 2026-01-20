import io
import textwrap
from pathlib import Path
from tests.helpers import prep_module


import pytest

p = prep_module("core", "jcamp")

# ---------- low level helpers ----------

def test_is_shape_valid_and_invalid():
    assert p.is_shape("1") == (1,)
    assert p.is_shape("2, 3") == (2, 3)
    assert p.is_shape("10,20,  30") == (10, 20, 30)

    # not pure integers - should return None
    assert p.is_shape("1.0, 2") is None
    assert p.is_shape("<A>, 2") is None


def test_to_number_int_float_and_fallback():
    assert p.to_number("10") == 10
    assert p.to_number("  -3  ") == -3
    assert p.to_number("3.14") == pytest.approx(3.14)
    assert p.to_number("1e-3") == pytest.approx(1e-3)
    assert p.to_number("not_a_number") == "not_a_number"


def test_split_tokens_angle_aware_keeps_angle_blocks():
    s = "<Alpha (X)> <Beta> gamma"
    tokens = p.split_tokens_angle_aware(s)
    assert tokens == ["<Alpha (X)>", "<Beta>", "gamma"]


def test_is_single_outer_paren_basic_cases():
    assert p.is_single_outer_paren("(1 2 3)")
    assert p.is_single_outer_paren("( (1 2), (3 4) )")

    # multiple top level groups - should be False
    assert not p.is_single_outer_paren("(1) (2)")
    assert not p.is_single_outer_paren("1 2 3")
    assert not p.is_single_outer_paren("(1 2 3")  # unbalanced


def test_split_top_level_commas_with_nested_parens_and_angles():
    s = "(1 2, 3 4), (5 6, 7 8), <A (B,C)>, 9"
    parts = p.split_top_level_commas(s)
    # top level commas only
    assert parts == [
        "(1 2, 3 4)",
        "(5 6, 7 8)",
        "<A (B,C)>",
        "9",
    ]


# ---------- shape - data splitting ----------

def test_split_shape_and_data_with_shape():
    # typical "( 3 )" shape followed by values
    shape, data = p.split_shape_and_data("( 3 ) 1 2 3")
    assert shape == (3,)
    assert data == "1 2 3"


def test_split_shape_and_data_without_shape_plain_value():
    # no leading shape - entire string is data
    shape, data = p.split_shape_and_data("10 20 30")
    assert shape is None
    assert data == "10 20 30"


def test_split_shape_and_data_angle_brackets_not_shape():
    # parentheses present but not a numeric shape, so treat whole as data
    raw = "( <First> , <Second> )"
    shape, data = p.split_shape_and_data(raw)
    assert shape is None
    assert data == raw.strip()


# ---------- leaf and nested parsing ----------

def test_parse_leaf_tokens_numbers_and_angle():
    text = "1 2.5 <Label (X)>"
    leaf = p.parse_leaf_tokens(text)
    # angle block should stay as one token
    assert leaf == [1, pytest.approx(2.5), "<Label (X)>"]


def test_parse_segment_simple_nested_tuple_like():
    seg = "((1 2 3, 4 5 6, <Read> <Phase> <Slice>, 0), 7, 8)"
    parsed = p.parse_segment(seg)

    # outermost should be list: [inner_group, 7, 8]
    assert isinstance(parsed, list)
    assert len(parsed) == 3
    inner = parsed[0]
    assert isinstance(inner, list)
    # first element of inner is another list of lists
    assert isinstance(inner[0], list)
    assert inner[1] == [4, 5, 6]
    assert inner[2] == ["<Read>", "<Phase>", "<Slice>"]
    assert inner[3] == 0


def test_parse_nested_simple_scalars_and_parens():
    # simple space separated
    assert p.parse_nested("1 2 3") == [1, 2, 3]

    # outer parens should be stripped
    assert p.parse_nested("(1 2 3)") == [1, 2, 3]

    # commas create list of segments
    s = "(1 2), (3 4), 5"
    parsed = p.parse_nested(s)
    assert parsed == [[1, 2], [3, 4], 5]


def test_parse_nested_with_angle_and_parens_refpow_like():
    # pattern similar to RefPowStat like "<System (Coil)>"
    s = "<System (Coil)>"
    parsed = p.parse_nested(s)
    assert parsed == "<System (Coil)>"


# ---------- end to end JCAMP parsing ----------

def _write_jcamp(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "example.jdx"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_parse_jcamp_from_path_basic_patterns(tmp_path):
    """End-to-end test hitting comments, scalars, shapes, angles, nested, and repeat."""

    jcamp_text = """
    ##TITLE=Test Parameter List
    ##JCAMPDX=4.24
    ##DATATYPE=Parameter Values
    $$ this is a comment line that should be captured
    $$ another comment

    ##$ScalarInt=42
    ##$ScalarFloat=3.5
    ##$YesNoFlag=Yes

    ##$ArrayWithShape=( 3 )
    10 20 30

    ##$AngleParam=( 2 )
    <Alpha (X)> <Beta>

    ##$NestedParam=( 1 )
    ((1 0 0, 0 1 0, 0 0 1), 3 3 3, <Read> <Phase> <Slice>, 0)

    ##$RepeatParam=( 4 )
    @4*(0)

    ##END=
    """

    path = _write_jcamp(tmp_path, jcamp_text)
    result = p.parse_jcamp_from_path(path)

    params = result["params"]
    comments = result["comments"]
    exceptions = result["exceptions"]

    # comments collected
    assert len(comments) == 2
    assert not all(line.startswith("$$") for line in comments)

    # no exceptions for this well formed sample
    assert exceptions == []

    # Scalar int
    assert params["$ScalarInt"]["shape"] is None
    assert params["$ScalarInt"]["data"] == 42

    # Scalar float
    assert params["$ScalarFloat"]["shape"] is None
    assert params["$ScalarFloat"]["data"] == pytest.approx(3.5)

    # Yes/No preserved as string
    assert params["$YesNoFlag"]["data"] == "Yes"

    # Array with numeric shape
    assert params["$ArrayWithShape"]["shape"] == (3,)
    assert params["$ArrayWithShape"]["data"] == [10, 20, 30]

    # Angle param with shape and <...> tokens preserved
    angle = params["$AngleParam"]
    assert angle["shape"] == (2,)
    assert angle["data"] == ["<Alpha (X)>", "<Beta>"]

    # Nested param, mainly check that it parses without breaking
    nested = params["$NestedParam"]
    assert nested["shape"] == (1,)
    assert isinstance(nested["data"], list)
    assert len(nested["data"]) == 4  # orientation, fov, labels, flag

    inner = nested["data"]
    assert isinstance(inner[0], list)
    assert inner[1] == [3, 3, 3]
    assert inner[2] == ["<Read>", "<Phase>", "<Slice>"]
    assert inner[3] == 0

    # Repeat param shape and raw pattern
    repeat = params["$RepeatParam"]
    assert repeat["shape"] == (4,)
    assert repeat["data"] == ["@4*", 0]


def test_parse_jcamp_from_text_and_bytes(tmp_path):
    text = """
    ##TITLE=From Text
    ##$Scalar=1
    """
    expected_key = "$Scalar"

    res_text = p.parse_jcamp_from_text(textwrap.dedent(text))
    res_bytes = p.parse_jcamp_from_bytes(textwrap.dedent(text).encode("utf-8"))

    assert expected_key in res_text["params"]
    assert expected_key in res_bytes["params"]
    assert res_text["params"][expected_key]["data"] == 1
    assert res_bytes["params"][expected_key]["data"] == 1


def test_parse_jcamp_from_file_like_stringio():
    buf = io.StringIO("##TITLE=Buf\n##$Val=2\n")
    res = p.parse_jcamp(buf)
    assert res["params"]["$Val"]["data"] == 2
    # 원본 스트림 위치는 복원되어야 함
    assert buf.tell() == 0


def test_parse_jcamp_from_file_like_bytesio():
    buf = io.BytesIO(b"##TITLE=Buf\n##$Val=3\n")
    res = p.parse_jcamp(buf)
    assert res["params"]["$Val"]["data"] == 3
    assert buf.tell() == 0


def test_jcamp_smoke():
    """Smoke test over all .jdx fixtures using p.run_smoke_test."""

    fixtures_dir = Path(__file__).parent / "fixtures"
    summary = p.run_smoke_test(fixtures_dir)

    # Basic smoke validation: parsing must not produce any hard errors
    assert summary["parse_errors"] == []
    # Exception entries should not appear for well-formed JCAMP files
    assert summary["files_with_exceptions"] == []
