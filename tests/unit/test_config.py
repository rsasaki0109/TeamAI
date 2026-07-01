from pathlib import Path

import pytest

from teamai.config.loader import TeamfileValidationError, load_team_config
from teamai.core.domain import AgentKind


def test_load_minimal_teamfile() -> None:
    config = load_team_config(Path("examples/minimal/team.yaml"))

    assert config.team.name == "minimal_team"
    assert config.agents["planner"].kind == AgentKind.PLANNER
    assert config.limits.max_tasks == 8


def test_load_pipeline_teamfile_without_planner() -> None:
    config = load_team_config(Path("examples/pipeline/team.yaml"))

    assert config.team.name == "pipeline_team"
    assert "planner" not in config.agents


def test_teamfile_rejects_unknown_agent_tool(tmp_path: Path) -> None:
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        source.replace("filesystem.write", "filesystem.delete"),
        encoding="utf-8",
    )

    with pytest.raises(TeamfileValidationError, match="unknown tool"):
        load_team_config(teamfile)


def test_teamfile_rejects_unknown_approval_target(tmp_path: Path) -> None:
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        source.replace(
            "require_approval_for:\n    - filesystem.write",
            "require_approval_for:\n    - filesystem.delete",
        ),
        encoding="utf-8",
    )

    with pytest.raises(TeamfileValidationError, match="unknown target"):
        load_team_config(teamfile)


def test_teamfile_rejects_openai_compatible_without_base_url(tmp_path: Path) -> None:
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile = tmp_path / "team.yaml"
    teamfile.write_text(
        source.replace("provider: fake", "provider: openai_compatible"),
        encoding="utf-8",
    )

    with pytest.raises(TeamfileValidationError, match="base_url"):
        load_team_config(teamfile)
