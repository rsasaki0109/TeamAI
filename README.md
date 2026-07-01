# TeamAI Runtime

TeamAI Runtime is a local-first Python runtime for running YAML-defined AI teams
with structured tasks, artifacts, reviews, and inspectable runs.

The MVP focuses on:

- Teamfiles as YAML configuration
- deterministic control in Python
- planner, specialist, critic, and finalizer agents
- capability-based routing
- bounded loops and budgets
- SQLite audit persistence
- safe filesystem tools
- fully offline tests through `FakeModelClient`

```bash
teamai init
teamai schema --output teamfile.schema.json
teamai validate team.yaml
teamai run team.yaml --input "Analyze this workspace and produce a short report" --yes
teamai run team.yaml --input "Analyze this workspace" --json
teamai inspect <run-id>
```

Python usage:

```python
from teamai import TeamRuntime

async with TeamRuntime.from_file("team.yaml") as runtime:
    result = await runtime.run(goal="Analyze this workspace and produce a short report")

print(result.final_output)
```

By default, the Python API rejects side-effect approvals unless an approval provider
is supplied. For trusted local demos, opt in explicitly:

```python
async with TeamRuntime.from_file("team.yaml", auto_approve=True) as runtime:
    result = await runtime.run(goal="Write a report file")
```

Real models use the `openai_compatible` provider. Set the API key in an environment
variable and point `base_url` at your endpoint:

```yaml
models:
  default:
    provider: openai_compatible
    model: gpt-4o-mini
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    capabilities:
      json_mode: true
      structured_output: false
      tool_calling: false
```

```bash
export OPENAI_API_KEY=sk-...
teamai run team.yaml --input "Summarize this workspace" --yes
```

Development checks:

```bash
uv sync --extra dev --locked
uv run python scripts/check_examples.py
uv run python scripts/check_import_rules.py
uv run pytest
uv run mypy src tests
uv run ruff check .
uv build
```

Release artifacts are built by GitHub Actions when a `v*` tag is pushed. The
release workflow uploads `dist/*` as a GitHub artifact and does not publish to
PyPI automatically.

Security reports should follow `SECURITY.md`. CodeQL runs on pushes, pull
requests, manual dispatch, and a weekly schedule.

Contribution and governance expectations are documented in `CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md`, and `GOVERNANCE.md`.
