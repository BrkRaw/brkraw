#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
CITATION_PATH = REPO_ROOT / "CITATION.cff"
BEGIN = "<!-- BEGIN: brkraw-bibtex -->"
END = "<!-- END: brkraw-bibtex -->"

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _bib_escape(s: str) -> str:
    # Minimal escaping for BibLaTeX
    # Keep it conservative to avoid mangling titles.
    s = s.replace("\\", "\\\\")
    s = s.replace("{", "\\{").replace("}", "\\}")
    return s


def _author_to_bib(a: dict[str, Any]) -> str:
    family = _norm(a.get("family-names", ""))
    given = _norm(a.get("given-names", ""))
    if family and given:
        return f"{family}, {given}"
    return family or given or ""


def _affiliations_to_note(authors: list[dict[str, Any]]) -> str:
    """Create a compact affiliations string for BibLaTeX."""
    parts: list[str] = []
    for a in authors or []:
        name = _author_to_bib(a)
        aff = a.get("affiliation")
        if not aff:
            continue
        if isinstance(aff, str):
            affs = [_norm(aff)] if _norm(aff) else []
        elif isinstance(aff, list):
            affs = [_norm(str(x)) for x in aff if _norm(str(x))]
        else:
            affs = []
        if not affs:
            continue
        if name:
            parts.append(f"{name}: " + "; ".join(affs))
        else:
            parts.append("; ".join(affs))

    if not parts:
        return ""
    return "Affiliations: " + " | ".join(parts)


def _pick_year(date_released: str) -> str:
    m = re.match(r"^\s*(\d{4})", date_released or "")
    return m.group(1) if m else ""


def _make_key(repo_url: str, year: str) -> str:
    slug = ""
    if repo_url:
        parts = repo_url.rstrip("/").split("/")
        slug = parts[-1] if parts else ""
    slug = re.sub(r"[^0-9A-Za-z]+", "", slug).lower() or "software"
    return f"{slug}_{year}" if year else slug


def cff_to_biblatex(
    cff: dict[str, Any],
    citekey: str | None = None,
    *,
    include_affiliations: bool = False,
) -> str:
    title = _norm(cff.get("title", ""))
    version = _norm(str(cff.get("version", "")))
    date_released = _norm(str(cff.get("date-released", "")))
    year = _pick_year(date_released)
    doi = _norm(str(cff.get("doi", "")))
    url = _norm(str(cff.get("url", "")))
    repo = _norm(str(cff.get("repository-code", "")))
    license_id = _norm(str(cff.get("license", "")))

    authors = cff.get("authors", []) or []
    author_strs = [a for a in (_author_to_bib(x) for x in authors) if a]
    author_field = " and ".join(author_strs)

    affiliations_note = _affiliations_to_note(authors) if include_affiliations else ""

    entry_type = "software"
    key = citekey or _make_key(repo or url, year)

    fields: list[tuple[str, str]] = []
    if author_field:
        fields.append(("author", author_field))
    if title:
        fields.append(("title", title))
    if year:
        fields.append(("year", year))
    if version:
        fields.append(("version", version))
    if doi:
        fields.append(("doi", doi))
    if repo:
        fields.append(("url", repo))
    elif url:
        fields.append(("url", url))
    if repo and url and (url != repo):
        fields.append(("note", f"Documentation: {url}"))
    if affiliations_note:
        fields.append(("addendum", affiliations_note))
    if license_id:
        fields.append(("license", license_id))
    if date_released:
        fields.append(("date", date_released))

    lines = [f"@{entry_type}{{{key},"]
    for k, v in fields:
        lines.append(f"  {k} = {{{_bib_escape(v)}}},")
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_biblatex() -> str:
    if not CITATION_PATH.exists():
        raise SystemExit("CITATION.cff not found.")
    cff = yaml.safe_load(CITATION_PATH.read_text(encoding="utf-8"))
    if not isinstance(cff, dict):
        raise SystemExit("Invalid CITATION.cff content (expected mapping).")
    out = cff_to_biblatex(cff)
    if not out.strip():
        raise SystemExit("BibLaTeX output is empty.")
    return out


def update_readme_block(biblatex: str) -> None:
    text = README_PATH.read_text(encoding="utf-8")

    pattern = re.compile(rf"{re.escape(BEGIN)}.*?{re.escape(END)}", re.DOTALL)
    replacement = f"{BEGIN}\n```biblatex\n{biblatex}```\n{END}"
    new_text, n = pattern.subn(replacement, text, count=1)

    if n != 1:
        raise SystemExit("Could not find unique README block markers.")

    if new_text != text:
        README_PATH.write_text(new_text, encoding="utf-8")
    else:
        print("README citation block already up to date.")


def main() -> int:
    biblatex = render_biblatex()
    update_readme_block(biblatex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
