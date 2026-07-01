from pathlib import Path
from typing import Any

import yaml


def test_ci_workflow_runs_mvp_checks() -> None:
    workflow = _load_workflow("ci.yml")

    assert workflow["name"] == "CI"
    assert workflow["permissions"]["contents"] == "read"
    assert _python_versions(workflow) == ["3.11", "3.12"]

    commands = _run_commands(workflow)
    assert "uv sync --extra dev --locked" in commands
    assert "uv run python scripts/check_examples.py" in commands
    assert "uv run python scripts/check_import_rules.py" in commands
    assert "uv run pytest" in commands
    assert "uv run mypy src tests" in commands
    assert "uv run ruff check ." in commands
    assert "uv build" in commands


def test_release_workflow_builds_distributions_without_publishing() -> None:
    workflow = _load_workflow("release.yml")

    assert workflow["name"] == "Release"
    assert workflow["permissions"]["contents"] == "write"

    commands = _run_commands(workflow, job_name="build")
    assert "uv sync --extra dev --locked" in commands
    assert "uv run python scripts/check_examples.py" in commands
    assert "uv run python scripts/check_import_rules.py" in commands
    assert "uv run pytest" in commands
    assert "uv run mypy src tests" in commands
    assert "uv run ruff check ." in commands
    assert "uv build" in commands

    upload_step = _step_named(workflow, "Upload distributions", job_name="build")
    assert upload_step["uses"] == "actions/upload-artifact@v4"
    assert upload_step["with"] == {
        "name": "python-distributions",
        "path": "dist/*",
        "if-no-files-found": "error",
    }

    release_step = _step_named(workflow, "Create GitHub Release", job_name="build")
    assert release_step["uses"] == "softprops/action-gh-release@v2"
    assert release_step["if"] == "startsWith(github.ref, 'refs/tags/')"
    assert release_step["with"] == {
        "files": "dist/*",
        "generate_release_notes": True,
    }


def test_codeql_workflow_analyzes_python() -> None:
    workflow = _load_workflow("codeql.yml")

    assert workflow["name"] == "CodeQL"
    assert workflow["permissions"] == {
        "contents": "read",
        "security-events": "write",
    }

    init_step = _step_named(workflow, "Initialize CodeQL", job_name="analyze")
    assert init_step["uses"] == "github/codeql-action/init@v3"
    assert init_step["with"] == {"languages": "python"}

    analyze_step = _step_named(workflow, "Perform CodeQL analysis", job_name="analyze")
    assert analyze_step["uses"] == "github/codeql-action/analyze@v3"


def _load_workflow(filename: str) -> dict[str, Any]:
    workflow_path = Path(".github/workflows") / filename
    return dict(yaml.safe_load(workflow_path.read_text(encoding="utf-8")))


def _python_versions(workflow: dict[str, Any]) -> list[str]:
    return list(workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"])


def _run_commands(workflow: dict[str, Any], *, job_name: str = "test") -> list[str]:
    steps = workflow["jobs"][job_name]["steps"]
    return [str(step["run"]) for step in steps if "run" in step]


def _step_named(
    workflow: dict[str, Any],
    step_name: str,
    *,
    job_name: str = "test",
) -> dict[str, Any]:
    steps = workflow["jobs"][job_name]["steps"]
    for step in steps:
        if step.get("name") == step_name:
            return dict(step)
    raise AssertionError(f"missing workflow step: {step_name}")
