from __future__ import annotations

from typing import Any

from teamai.config.models import TeamConfig


def generate_teamfile_schema() -> dict[str, Any]:
    schema = TeamConfig.model_json_schema()
    schema["title"] = "Teamfile"
    return schema
