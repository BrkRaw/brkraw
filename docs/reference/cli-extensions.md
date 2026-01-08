# CLI plugins (overview)

BrkRaw supports extensibility not only at the conversion level (rules, specs,
converter hooks) but also at the CLI level.

CLI plugins are Python packages that add new `brkraw` subcommands via entry
points. They are the recommended approach for new workflows and tools that
should live outside the core repository.

## When to use a CLI plugin

- Add a new top-level command (for example `brkraw viewer`).
- Build project-specific workflows on top of the BrkRaw API.
- Provide interactive tooling (GUI/QA/automation) without changing core.

## Relationship to hooks

- Converter hooks customize conversion behavior.
- CLI plugins customize how users interact with BrkRaw.

## Developer guide

For authoring and packaging, see `docs/dev/cli-extensions.md`.
