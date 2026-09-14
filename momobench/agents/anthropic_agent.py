"""Anthropic provider adapter (spec §47). Uses the Messages API, which is
stateless when called directly — the full explicit transcript is sent every
turn. No assistant-prefill tricks (not uniformly supported and would break
cross-provider comparability)."""

from __future__ import annotations

import time

from anthropic import AsyncAnthropic

from momobench.agents.base import BaseAgent
from momobench.agents.schema import AgentResponse


class AnthropicAgent(BaseAgent):
    provider = "anthropic"

    def __init__(self, model: str) -> None:
        self.model = model
        self.client = AsyncAnthropic()

    async def act(self, system_prompt: str, messages: list[dict], max_output_tokens: int) -> AgentResponse:
        t0 = time.perf_counter()

        r = await self.client.messages.create(
            model=self.model,
            system=system_prompt,
            max_tokens=max_output_tokens,
            messages=messages,
        )

        txt = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")

        dt = (time.perf_counter() - t0) * 1000
        usage = getattr(r, "usage", None)

        return AgentResponse(
            text=txt,
            provider=self.provider,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            latency_ms=dt,
            request_id=getattr(r, "id", None),
            raw_finish_reason=getattr(r, "stop_reason", None),
        )
