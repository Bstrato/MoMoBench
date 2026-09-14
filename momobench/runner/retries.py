"""Transport-only API retries (spec §53). Distinct from *behavioral*
retries: a malformed or unsafe agent action is benchmark behavior and must
be handled inside the episode (the parser / scorer), never silently retried
here. This layer only resends an identical request after a transient
network/rate-limit/server error.
"""

from __future__ import annotations

import tenacity

from momobench.agents.base import BaseAgent
from momobench.agents.schema import AgentResponse

TRANSIENT_NAME_MARKERS = (
    "Timeout",
    "ConnectionError",
    "ConnectTimeout",
    "APIConnectionError",
    "RateLimitError",
    "InternalServerError",
    "ServiceUnavailable",
)


def is_transport_error(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    try:
        status_int = int(status) if status is not None else None
    except (TypeError, ValueError):
        status_int = None
    if status_int == 429 or (status_int is not None and 500 <= status_int < 600):
        return True
    name = type(exc).__name__
    return any(marker in name for marker in TRANSIENT_NAME_MARKERS)


class RetryingAgent(BaseAgent):
    """Wraps any ``BaseAgent`` with exponential-backoff transport retries.
    Never changes the prompt between attempts and never retries because a
    *decision* looked wrong — only 429/5xx/timeout/connection errors."""

    def __init__(
        self,
        inner: BaseAgent,
        *,
        max_attempts: int = 5,
        initial_wait: float = 1.0,
        max_wait: float = 30.0,
    ) -> None:
        self._inner = inner
        self.provider = inner.provider
        self.model = getattr(inner, "model", inner.provider)
        self._retrying = tenacity.AsyncRetrying(
            stop=tenacity.stop_after_attempt(max_attempts),
            wait=tenacity.wait_exponential(multiplier=initial_wait, max=max_wait) + tenacity.wait_random(0, 1),
            retry=tenacity.retry_if_exception(is_transport_error),
            reraise=True,
        )

    async def act(self, system_prompt: str, messages: list[dict], max_output_tokens: int) -> AgentResponse:
        async for attempt in self._retrying:
            with attempt:
                return await self._inner.act(system_prompt, messages, max_output_tokens)
        raise AssertionError("unreachable: tenacity always returns or raises")
