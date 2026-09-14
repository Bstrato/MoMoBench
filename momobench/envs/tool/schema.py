"""Tool-call action schema for the structured tool interface (spec §100).
Distinct from the USSD ``AgentAction`` grammar (menu navigation) by design —
tool calls carry named arguments instead of a single positional ``value``.
Parsing follows the same deterministic, never-LLM-repaired approach as
``actions/parser.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ValidationError

ToolName = Literal[
    "get_balance",
    "resolve_recipient",
    "prepare_transfer",
    "confirm_transfer",
    "cancel_transfer",
    "get_transaction_status",
    "get_transaction_history",
    "wait",
    "finish",
]

STANDARD_TOOL_FORMAT_ERROR = (
    "Invalid tool call format. Return one valid JSON object with a 'tool' field "
    "using one of the available tools."
)


class ToolAction(BaseModel):
    tool: ToolName
    arguments: dict = {}


@dataclass(frozen=True)
class ToolParseResult:
    action: ToolAction | None
    error: str | None

    @property
    def ok(self) -> bool:
        return self.action is not None


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_tool_action(text: str) -> ToolParseResult:
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
            action = ToolAction.model_validate(data)
        except ValidationError:
            continue
        return ToolParseResult(action=action, error=None)

    return ToolParseResult(action=None, error=STANDARD_TOOL_FORMAT_ERROR)
