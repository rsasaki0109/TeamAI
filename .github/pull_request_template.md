## Summary

Describe the change and why it is needed.

## Verification

- [ ] `uv run python scripts/check_examples.py`
- [ ] `uv run python scripts/check_import_rules.py`
- [ ] `uv run pytest`
- [ ] `uv run mypy src tests`
- [ ] `uv run ruff check .`
- [ ] `uv build`

## Runtime Safety

- [ ] No unbounded loops or retries were added.
- [ ] Side effects still require explicit approval.
- [ ] Workspace boundaries and redaction rules are preserved.
- [ ] New model, tool, or persistence behavior is covered by tests.

## Notes

Mention compatibility, migration, or security implications.
