"""Local vLLM provider adapter. Talks to vLLM's OpenAI-compatible
chat-completions endpoint over a configurable base URL — unlike
``OpenAIAgent``, which uses OpenAI's Responses API that vLLM does not
implement. No request leaves the host running the vLLM server; not billed."""

from __future__ import annotations

import os
import time

from openai import AsyncOpenAI

from momobench.agents.base import BaseAgent
from momobench.agents.schema import AgentResponse

DEFAULT_BASE_URL = "http://localhost:8000/v1"


class VLLMAgent(BaseAgent):
    provider = "vllm"

    def __init__(self, model: str) -> None:
        self.model = model
        base_url = os.environ.get("VLLM_BASE_URL", DEFAULT_BASE_URL)
        api_key = os.environ.get("VLLM_API_KEY") or "vllm-local"
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

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
