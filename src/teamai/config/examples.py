from __future__ import annotations

from pathlib import Path

from teamai.config.loader import TeamfileValidationError, load_team_config

EXAMPLE_LINE_LIMIT = 120


def check_examples(repo_root: Path) -> list[str]:
    teamfiles = sorted((repo_root / "examples").glob("*/team.yaml"))
    errors: list[str] = []
    if not teamfiles:
        return ["no example Teamfiles found"]
    for teamfile in teamfiles:
        errors.extend(check_teamfile(teamfile, repo_root=repo_root))
    return errors


def check_teamfile(
    teamfile: Path,
    *,
    repo_root: Path,
    max_lines: int = EXAMPLE_LINE_LIMIT,
) -> list[str]:
    errors: list[str] = []
    relative_path = _relative_path(teamfile, repo_root)
    line_count = len(teamfile.read_text(encoding="utf-8").splitlines())
    if line_count > max_lines:
        errors.append(f"{relative_path}: expected <= {max_lines} lines, found {line_count}")
    try:
        config = load_team_config(teamfile)
    except TeamfileValidationError as exc:
        errors.append(f"{relative_path}: invalid Teamfile: {exc}")
        return errors
    non_fake_models = [
        name for name, model in config.models.items() if model.provider != "fake"
    ]
    if non_fake_models:
        joined = ", ".join(non_fake_models)
        errors.append(f"{relative_path}: example models must use fake provider: {joined}")
    return errors


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()
