"""OpenAI provider adapter (spec §46). Uses the Responses API. Thin by
design — no benchmark logic here, only request/response translation."""

from __future__ import annotations

import time

from openai import AsyncOpenAI

from momobench.agents.base import BaseAgent
from momobench.agents.schema import AgentResponse


class OpenAIAgent(BaseAgent):
    provider = "openai"

    def __init__(self, model: str) -> None:
        self.model = model
        self.client = AsyncOpenAI()

    async def act(self, system_prompt: str, messages: list[dict], max_output_tokens: int) -> AgentResponse:
        t0 = time.perf_counter()

        inp = [{"role": "developer", "content": system_prompt}, *messages]

        r = await self.client.responses.create(
            model=self.model,
            input=inp,
            max_output_tokens=max_output_tokens,
        )

        dt = (time.perf_counter() - t0) * 1000
        usage = getattr(r, "usage", None)

        return AgentResponse(
            text=r.output_text,
            provider=self.provider,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            latency_ms=dt,
            request_id=getattr(r, "id", None),
            raw_finish_reason=None,
        )
