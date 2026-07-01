from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "content",
    "password",
    "preview",
    "secret",
    "token",
)

MAX_LOG_STRING_LENGTH = 512
MAX_PREVIEW_LENGTH = 2_000


def redact(value: Any, *, max_string_length: int = MAX_LOG_STRING_LENGTH) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                redacted[key_text] = _redacted_marker(item)
            else:
                redacted[key_text] = redact(item, max_string_length=max_string_length)
        return redacted
    if isinstance(value, str):
        return truncate(value, max_length=max_string_length)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        return [redact(item, max_string_length=max_string_length) for item in value]
    return value


def truncate(value: str, *, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    omitted = len(value) - max_length
    return f"{value[:max_length]}...<truncated {omitted} chars>"


def approval_preview(action: str, arguments: Mapping[str, object]) -> str | None:
    if action != "filesystem.write":
        return None
    path = arguments.get("path")
    content = arguments.get("content")
    if not isinstance(content, str):
        return None
    path_text = str(path) if isinstance(path, str) else "<unknown>"
    return (
        f"Path: {path_text}\n"
        f"Content preview:\n{truncate(content, max_length=MAX_PREVIEW_LENGTH)}"
    )


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _redacted_marker(value: Any) -> str:
    if isinstance(value, str):
        if value.startswith("<redacted "):
            return value
        return f"<redacted string chars={len(value)}>"
    if isinstance(value, bytes | bytearray):
        return f"<redacted bytes len={len(value)}>"
    return f"<redacted {type(value).__name__}>"
