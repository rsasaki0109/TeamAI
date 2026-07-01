from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from teamai.config.models import TeamConfig


class TeamfileValidationError(Exception):
    """Raised when a Teamfile cannot be loaded or validated."""


def load_team_config(path: str | Path) -> TeamConfig:
    teamfile_path = Path(path)
    try:
        raw = yaml.safe_load(teamfile_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TeamfileValidationError(f"could not read Teamfile: {teamfile_path}") from exc
    if not isinstance(raw, dict):
        raise TeamfileValidationError("Teamfile must be a YAML mapping")
    data: dict[str, Any] = raw
    try:
        return TeamConfig.model_validate(data)
    except ValidationError as exc:
        raise TeamfileValidationError(str(exc)) from exc
