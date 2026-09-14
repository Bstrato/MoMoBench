"""Together AI provider adapter (spec §48). Uses the chat-completions
interface with the common-denominator parameter set only (messages,
max_tokens) — reasoning/temperature/tool-call options are not assumed
uniform across Together-hosted models and are not used unless an
experimental protocol explicitly calls for them."""

from __future__ import annotations

import time

from together import AsyncTogether

from momobench.agents.base import BaseAgent
from momobench.agents.schema import AgentResponse


class TogetherAgent(BaseAgent):
    provider = "together"

    def __init__(self, model: str) -> None:
        self.model = model
        self.client = AsyncTogether()

    async def act(self, system_prompt: str, messages: list[dict], max_output_tokens: int) -> AgentResponse:
        t0 = time.perf_counter()

        req = [{"role": "system", "content": system_prompt}, *messages]

        r = await self.client.chat.completions.create(
            model=self.model,
            messages=req,
            max_tokens=max_output_tokens,
        )

        txt = r.choices[0].message.content or ""

        dt = (time.perf_counter() - t0) * 1000
        usage = getattr(r, "usage", None)

        return AgentResponse(
            text=txt,
            provider=self.provider,
            model=self.model,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            latency_ms=dt,
            request_id=getattr(r, "id", None),
            raw_finish_reason=getattr(r.choices[0], "finish_reason", None),
        )
