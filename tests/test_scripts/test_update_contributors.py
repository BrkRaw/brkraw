from __future__ import annotations

import scripts.update_contributors as uc


def test_render_markdown_list_renders_only_login_when_login_present() -> None:
    assert (
        uc._render_markdown_list([{"login": "dvm-shlee", "name": "SungHo Lee"}])
        == "- [dvm-shlee](https://github.com/dvm-shlee)"
    )


def test_render_markdown_list_falls_back_to_login_when_no_name() -> None:
    assert (
        uc._render_markdown_list([{"login": "dvm-shlee", "name": ""}])
        == "- [dvm-shlee](https://github.com/dvm-shlee)"
    )


def test_render_markdown_list_renders_plain_name_when_no_login() -> None:
    assert uc._render_markdown_list([{"login": "", "name": "SungHo Lee"}]) == "- SungHo Lee"


def test_avatar_url_with_size_uses_github_size_param() -> None:
    assert (
        uc._avatar_url_with_size("https://github.com/dvm-shlee.png", size=96)
        == "https://github.com/dvm-shlee.png?size=96"
    )


def test_render_github_avatar_table_includes_label_under_avatar() -> None:
    table = uc._render_github_avatar_table([{"login": "dvm-shlee", "name": "SungHo Lee"}], per_row=6)
    assert "[![SungHo Lee][dvm-shlee-avatar]][dvm-shlee]<br>SungHo Lee" in table


def test_normalize_git_items_merges_same_email() -> None:
    normalized = uc._normalize_git_items(
        [
            {"name": "SungHo Lee", "email": "shlee@unc.edu", "count": "3", "login": ""},
            {"name": "dvm-shlee", "email": "shlee@unc.edu", "count": "2", "login": "dvm-shlee"},
        ]
    )
    assert normalized == [{"login": "dvm-shlee", "name": "SungHo Lee"}]
