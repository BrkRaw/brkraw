#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
CITATION_PATH = REPO_ROOT / "CITATION.cff"
CFF_TO_BIBLATEX = REPO_ROOT / "scripts" / "cff_to_biblatex.py"

BEGIN = "<!-- BEGIN: brkraw-bibtex -->"
END = "<!-- END: brkraw-bibtex -->"


def run(args: list[str]) -> str:
    p = subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True)
    if p.returncode != 0:
        msg = p.stderr.strip() or p.stdout.strip()
        raise SystemExit(f"{args[0]} failed: {msg}")
    return p.stdout


def render_biblatex() -> str:
    if not CITATION_PATH.exists():
        raise SystemExit("CITATION.cff not found.")
    if not CFF_TO_BIBLATEX.exists():
        raise SystemExit(f"Missing script: {CFF_TO_BIBLATEX}")
    out = run(["python", str(CFF_TO_BIBLATEX), "--infile", str(CITATION_PATH)])
    out = out.strip()
    if not out:
        raise SystemExit("BibLaTeX output is empty.")
    return out + "\n"


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
