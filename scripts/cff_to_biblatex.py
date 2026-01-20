#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


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
    """Create a compact affiliations string for BibLaTeX.

    BibLaTeX does not have a standard `affiliation` field, so we store it in
    `addendum` (preferred) or append into `note`.

    Format:
      Affiliations: Family, Given: Aff1; Aff2 | Family2, Given2: Aff1; Aff2

    Only authors that have an `affiliation` value are included.
    """
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
            # Unknown type - ignore
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
    # Example: https://github.com/BrkRaw/brkraw -> brkraw_2026
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
    # Prefer repository URL as main url if available
    if repo:
        fields.append(("url", repo))
    elif url:
        fields.append(("url", url))
    # Keep docs url as note if both exist
    if repo and url and (url != repo):
        fields.append(("note", f"Documentation: {url}"))
    if affiliations_note:
        # Prefer addendum for extra metadata (BibLaTeX has no standard affiliation field)
        fields.append(("addendum", affiliations_note))
    if license_id:
        fields.append(("license", license_id))
    if date_released:
        # BibLaTeX understands date = YYYY-MM-DD
        fields.append(("date", date_released))

    lines = [f"@{entry_type}{{{key},"]
    for k, v in fields:
        lines.append(f"  {k} = {{{_bib_escape(v)}}},")
    # Remove trailing comma on last field if exists
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Convert CITATION.cff to a BibLaTeX @software entry.")
    p.add_argument("--infile", default="CITATION.cff", help="Path to CITATION.cff")
    p.add_argument("--outfile", default=None, help="Write output to file (optional)")
    p.add_argument("--citekey", default=None, help="Override citekey (optional)")
    p.add_argument(
        "--include-affiliations",
        action="store_true",
        help="Include author affiliations as `addendum` (may be long).",
    )
    args = p.parse_args()

    inpath = Path(args.infile)
    if not inpath.exists():
        raise SystemExit(f"Input not found: {inpath}")

    cff = yaml.safe_load(inpath.read_text(encoding="utf-8"))
    if not isinstance(cff, dict):
        raise SystemExit("Invalid CITATION.cff content (expected mapping).")

    out = cff_to_biblatex(
        cff,
        citekey=args.citekey,
        include_affiliations=bool(getattr(args, "include_affiliations", False)),
    )

    if args.outfile:
        Path(args.outfile).write_text(out, encoding="utf-8")
    else:
        print(out, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
