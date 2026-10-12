from brkraw.cli.commands import convert as convert_cmd


def test_parse_hook_args_tuple_default() -> None:
    parsed = convert_cmd._parse_hook_args(["hook:key=1,2,3"])
    assert parsed["hook"]["key"] == (1, 2, 3)


def test_parse_hook_args_bracketed_list() -> None:
    parsed = convert_cmd._parse_hook_args(["hook:key=[1,2,3]"])
    assert parsed["hook"]["key"] == [1, 2, 3]


def test_parse_hook_args_bracketed_tuple() -> None:
    parsed = convert_cmd._parse_hook_args(["hook:key=(1,2,3)"])
    assert parsed["hook"]["key"] == (1, 2, 3)


def test_parse_hook_args_nested_list() -> None:
    parsed = convert_cmd._parse_hook_args(["hook:key=[[1,2],[3,4]]"])
    assert parsed["hook"]["key"] == [[1, 2], [3, 4]]
