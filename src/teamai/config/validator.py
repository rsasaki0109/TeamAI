from __future__ import annotations

from pathlib import Path

from teamai.config.loader import load_team_config
from teamai.config.models import TeamConfig


def validate_teamfile(path: str | Path) -> TeamConfig:
    return load_team_config(path)
