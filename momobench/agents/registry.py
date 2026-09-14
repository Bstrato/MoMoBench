"""Agent lookup. Mock agents (oracle/naive/random) are always available with
no configuration. Real provider agents are looked up from
``config/agents.yaml`` (spec §9) — the configured roster is treated as the
source of truth: an unavailable model is reported as unavailable, never
silently substituted (spec §119).
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from momobench.agents.base import BaseAgent
from momobench.agents.mock_agents import NaiveAgent, OracleAgent, RandomAgent
from momobench.scenarios.schema import Scenario
from momobench.utils.io import load_yaml

AgentFactory = Callable[[Scenario | None], BaseAgent]

MOCK_AGENT_FACTORIES: dict[str, AgentFactory] = {
    "oracle": lambda scenario: OracleAgent(scenario),
    "naive": lambda scenario: NaiveAgent(),
    "random": lambda scenario: RandomAgent(seed=scenario.seed if scenario is not None else 0),
}

MOCK_AGENT_KEYS = frozenset(MOCK_AGENT_FACTORIES)

PROVIDER_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "together": "TOGETHER_API_KEY",
    "vllm": "VLLM_BASE_URL",
}


def is_mock_agent(agent_key: str) -> bool:
    return agent_key in MOCK_AGENT_KEYS


def build_mock_agent(agent_key: str, scenario: Scenario | None) -> BaseAgent:
    if agent_key not in MOCK_AGENT_FACTORIES:
        raise KeyError(f"unknown mock agent key: {agent_key!r}")
    return MOCK_AGENT_FACTORIES[agent_key](scenario)


@dataclass(frozen=True)
class AgentConfigEntry:
    key: str
    provider: str
    model: str
    display_name: str


def load_agents_config(path: str | Path) -> dict[str, AgentConfigEntry]:
    data = load_yaml(path)
    entries: dict[str, AgentConfigEntry] = {}
    for key, spec in data["agents"].items():
        entries[key] = AgentConfigEntry(
            key=key,
            provider=spec["provider"],
            model=spec["model"],
            display_name=spec.get("display_name", key),
        )
    return entries


def build_real_agent(entry: AgentConfigEntry) -> BaseAgent:
    if entry.provider == "openai":
        from momobench.agents.openai_agent import OpenAIAgent

        return OpenAIAgent(entry.model)
    if entry.provider == "anthropic":
        from momobench.agents.anthropic_agent import AnthropicAgent

        return AnthropicAgent(entry.model)
    if entry.provider == "together":
        from momobench.agents.together_agent import TogetherAgent

        return TogetherAgent(entry.model)
    if entry.provider == "vllm":
        from momobench.agents.vllm_agent import VLLMAgent

        return VLLMAgent(entry.model)
    raise ValueError(f"unknown provider: {entry.provider!r}")


def get_agent_factory(agent_key: str, agents_config: dict[str, AgentConfigEntry] | None = None) -> AgentFactory:
    """Uniform lookup used by the runner for every agent kind — mock or
    real. Real agents are constructed once and cached (an API client is
    scenario-independent); the factory signature stays ``(scenario) ->
    BaseAgent`` throughout so the episode runner never special-cases agent
    kind."""
    if is_mock_agent(agent_key):
        return lambda scenario: build_mock_agent(agent_key, scenario)

    if not agents_config or agent_key not in agents_config:
        raise KeyError(f"unknown agent key: {agent_key!r}")

    entry = agents_config[agent_key]
    cache: dict[str, BaseAgent] = {}

    def factory(_scenario: Scenario | None) -> BaseAgent:
        if "agent" not in cache:
            cache["agent"] = build_real_agent(entry)
        return cache["agent"]

    return factory


# -- preflight (spec §10) ------------------------------------------------


@dataclass(frozen=True)
class PreflightResult:
    agent_key: str
    provider: str
    model: str
    display_name: str
    available: bool
    error: str | None
    checked_at: str

    def to_json_dict(self) -> dict:
        return {
            "agent_key": self.agent_key,
            "provider": self.provider,
            "model": self.model,
            "display_name": self.display_name,
            "available": self.available,
            "error": self.error,
            "checked_at": self.checked_at,
        }


async def preflight_agent(entry: AgentConfigEntry) -> PreflightResult:
    checked_at = dt.datetime.now(dt.UTC).isoformat()

    env_var = PROVIDER_ENV_VARS.get(entry.provider)
    if env_var is None:
        return PreflightResult(
            entry.key, entry.provider, entry.model, entry.display_name, False,
            f"unknown provider {entry.provider!r}", checked_at,
        )
    if entry.provider != "vllm" and not os.environ.get(env_var):
        return PreflightResult(
            entry.key, entry.provider, entry.model, entry.display_name, False,
            f"missing environment variable {env_var}", checked_at,
        )

    try:
        if entry.provider == "openai":
            from openai import AsyncOpenAI

            client = AsyncOpenAI()
            await client.models.retrieve(entry.model)
        elif entry.provider == "anthropic":
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic()
            await client.models.retrieve(entry.model)
        elif entry.provider == "together":
            from together import AsyncTogether

            client = AsyncTogether()
            models = await client.models.list()
            ids = {getattr(m, "id", None) for m in models}
            if entry.model not in ids:
                raise LookupError(f"model {entry.model!r} not found in Together model list")
        elif entry.provider == "vllm":
            from openai import AsyncOpenAI

            from momobench.agents.vllm_agent import DEFAULT_BASE_URL

            base_url = os.environ.get("VLLM_BASE_URL", DEFAULT_BASE_URL)
            api_key = os.environ.get("VLLM_API_KEY") or "vllm-local"
            client = AsyncOpenAI(base_url=base_url, api_key=api_key)
            models = await client.models.list()
            ids = {getattr(m, "id", None) for m in models.data}
            if entry.model not in ids:
                raise LookupError(
                    f"model {entry.model!r} not found on vLLM server at {base_url} (served: {sorted(ids)})"
                )
        else:
            raise ValueError(f"unknown provider: {entry.provider!r}")
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any provider error means "unavailable"
        return PreflightResult(
            entry.key, entry.provider, entry.model, entry.display_name, False, str(exc), checked_at
        )

    return PreflightResult(entry.key, entry.provider, entry.model, entry.display_name, True, None, checked_at)


async def preflight_all(agents_config: dict[str, AgentConfigEntry]) -> list[PreflightResult]:
    results = []
    for entry in agents_config.values():
        results.append(await preflight_agent(entry))
    return results
