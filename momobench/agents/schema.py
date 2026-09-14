"""Provider-independent agent request/response types (spec §44). Every
adapter — real provider or mock — normalizes to ``AgentResponse``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRequest:
    system_prompt: str
    messages: list[dict]
    max_output_tokens: int


@dataclass(frozen=True)
class AgentResponse:
    text: str
    provider: str
    model: str

    input_tokens: int | None
    output_tokens: int | None

    latency_ms: float
    request_id: str | None

    raw_finish_reason: str | None
