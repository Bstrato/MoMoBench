"""Deterministic parsing of raw model output into an ``AgentAction`` (spec
§27). Never uses another LLM to repair malformed output — on failure, the
environment state does not change and the caller (the episode runner) is
responsible for consuming a step and re-prompting with a standard error."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from momobench.actions.schema import AgentAction

STANDARD_FORMAT_ERROR = "Invalid action format. Return one valid JSON action using the available actions."


@dataclass(frozen=True)
class ParseResult:
    action: AgentAction | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.action is not None


def _extract_first_json_object(text: str) -> str | None:
    """Deterministically extract the first balanced {...} substring, so a
    model that wraps its JSON in prose can still self-correct via the
    standard error message without any LLM-based repair."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_action(text: str) -> ParseResult:
    stripped = text.strip()

    candidates = [stripped]
    extracted = _extract_first_json_object(stripped)
    if extracted is not None and extracted != stripped:
        candidates.append(extracted)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        try:
            action = AgentAction.model_validate(data)
        except ValidationError:
            continue
        return ParseResult(action=action, error=None)

    return ParseResult(action=None, error=STANDARD_FORMAT_ERROR)
