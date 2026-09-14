"""Common agent interface. Every provider adapter and every mock agent
implements exactly this — the episode runner never special-cases an agent
type (spec §44)."""

from __future__ import annotations

from momobench.agents.schema import AgentResponse


class BaseAgent:
    provider: str = "unknown"
    model: str = "unknown"

    async def act(self, system_prompt: str, messages: list[dict], max_output_tokens: int) -> AgentResponse:
        raise NotImplementedError
