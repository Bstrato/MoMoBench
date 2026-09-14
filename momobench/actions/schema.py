"""The common agent action grammar (spec §26). Every model, regardless of
provider, outputs exactly one action per turn in this schema — provider
adapters transform request syntax only, never the action vocabulary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ActionType = Literal[
    "select",
    "enter",
    "confirm",
    "cancel",
    "back",
    "check_history",
    "check_status",
    "wait",
    "finish",
]


class AgentAction(BaseModel):
    action: ActionType
    value: str | None = None
