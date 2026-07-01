# Contributing

TeamAI Runtime is built around deterministic control, structured tasks, bounded
execution, and inspectable artifacts. Contributions should preserve those
properties.

## Development Setup

```bash
uv sync --extra dev --locked
uv run python scripts/check_examples.py
uv run python scripts/check_import_rules.py
uv run pytest
uv run mypy src tests
uv run ruff check .
uv build
```

Tests must not require external APIs. Use `FakeModelClient` for offline model
behavior and inject test doubles for provider contracts.

## Design Constraints

- Keep core runtime code independent from provider adapters.
- Treat YAML as configuration, not a programming language.
- Keep all loops bounded by explicit limits.
- Store structured artifacts and events instead of free-form chat transcripts.
- Require explicit approval for side effects unless a caller opts into
  auto-approval.
- Keep examples small and runnable with the fake provider.

## Pull Requests

Before opening a pull request, run the development checks above. Include a short
summary, test evidence, and any security or compatibility implications.
