from brkraw.core.formatter import format_data


def test_format_data_color_value():
    data = {"value": {"value": "OK", "color": "red"}}
    rendered = format_data(data, "{value}", indent=0)
    assert rendered == "\033[31mOK\033[0m"


def test_format_data_color_alignment():
    data = {"value": {"value": "OK", "align": "right", "size": 4, "fill": ".", "color": "green"}}
    rendered = format_data(data, "{value}", indent=0)
    assert rendered == "\033[32m..OK\033[0m"
