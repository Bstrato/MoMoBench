"""Secret redaction. Every writer in this package must pass text/dicts
through here before they touch disk — API keys must never be logged (spec
§58, §92)."""

from __future__ import annotations

import os
from typing import Any

_SECRET_ENV_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TOGETHER_API_KEY")


def _current_secret_values() -> list[str]:
    return [v for var in _SECRET_ENV_VARS if (v := os.environ.get(var))]


def redact_text(text: str) -> str:
    for secret in _current_secret_values():
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_value(v) for v in value)
    return value
