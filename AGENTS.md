# Codex instructions (repo-wide)

## Environment
- Use the project-local virtualenv at `.venv` (interpreter: `.venv/bin/python`) when running Python commands.
- Target Python version for development: >= 3.8. If a change would break
 versions supported by `pyproject.toml`, call it out before proceeding.

## Project constraints
- This repository is a Python package.
- Prefer pure functions and type hints.
- Do not introduce new dependencies unless explicitly requested.
- Follow existing style and naming conventions.
- Avoid large refactors unless requested.

## Quality bar
- Add or update tests for behavior changes when practical.
- Keep user-facing CLI output stable unless explicitly requested.
- Prefer clear errors over silent failures; avoid broad `except Exception` unless there is a strong reason.

## Handy commands
- Run tests: `.venv/bin/python -m pytest`
- Lint/type check: only run tools already configured in the repo (do not add new tooling unless asked).
