# Documentation contribution guidelines

This project uses MkDocs (`mkdocs.yml`) with Markdown files under `docs/`.
The goal is to keep documentation consistent, reviewable, and easy to maintain.

---

## Where content should live

- `docs/getting-started/`: onboarding and quickstarts.
- `docs/cli/`: user-facing CLI behavior and examples.
- `docs/api/`: Python API usage and reference-style guides.
- `docs/reference/`: concepts, formats, and semantics (user-facing).
- `docs/dev/`: contributor-facing guidance (how to build/extend/maintain).

Rule of thumb:

- If a reader needs it to *use* BrkRaw → keep it in `getting-started/`, `cli/`,
  `api/`, or `reference/`.
- If a reader needs it to *contribute to or extend* BrkRaw → put it in `dev/`.

---

## Writing style

- Prefer short sections with clear headings.
- Use consistent terminology:
  - addons = rules/specs/transforms/pruner specs (case-dependent customization)
  - plugins = hook packages + CLI plugins (new functionality via entry points)
- Keep “rules” vs “recommendations” explicit when defining policies.
- Prefer concrete examples (YAML snippets, CLI commands, directory layouts).
- Avoid duplicating content across pages; link instead.

---

## Examples and commands

- Wrap paths/commands/identifiers in backticks.
- Use fenced blocks with language tags (`bash`, `yaml`, `toml`, `python`).
- Prefer examples that work on macOS/Linux shells unless otherwise stated.

---

## Updating navigation

- If you add a new page, add it to `mkdocs.yml` under the appropriate section.
- Use clear, stable nav labels (avoid frequent renames).

---

## PR checklist (docs)

- Page is placed in the correct section (`reference/` vs `dev/`).
- No redundant copy/paste across pages; cross-links added where appropriate.
- Examples are syntactically valid (YAML/TOML/commands).
- New terms are defined on first use or linked to the relevant reference page.
- `mkdocs.yml` nav updated when adding pages.

