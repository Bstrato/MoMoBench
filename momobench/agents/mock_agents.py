"""Deterministic mock agents used as benchmark/evaluator controls before any
real LLM is involved (spec §43). If OracleAgent doesn't score ~100% on a
valid scenario suite, the benchmark itself is wrong, not the agent.

OracleAgent is a *privileged* test fixture: unlike every other agent (mock
or real), it is constructed with the episode's ``Scenario`` ground truth, so
it can implement "the intended safe policy" directly rather than needing to
infer intent from text. NaiveAgent and RandomAgent are ordinary
observation-text-only agents — exactly the interface a real LLM adapter
uses — so their failures are meaningful evidence that the benchmark/scorer
can tell behaviors apart (spec §115: "if all three controls score similarly,
the benchmark is not informative").
"""

from __future__ import annotations

import json
import random

from momobench.agents._text import (
    available_action_types,
    classify_screen,
    find_menu_key,
    last_history_status,
    latest_observation,
    menu_items,
    result_message,
    status_value,
    task_amount,
    task_phone,
)
from momobench.agents.base import BaseAgent
from momobench.agents.schema import AgentResponse
from momobench.scenarios.schema import Scenario


def _mock_response(action: dict, *, provider: str, model: str) -> AgentResponse:
    return AgentResponse(
        text=json.dumps(action),
        provider=provider,
        model=model,
        input_tokens=None,
        output_tokens=None,
        latency_ms=0.0,
        request_id=None,
        raw_finish_reason=None,
    )


class OracleAgent(BaseAgent):
    """Knows the visible environment and follows the intended safe policy
    (spec §43): correct recipient/amount, correct route declaration, cancels
    on any block, and verifies status/history before ever retrying instead
    of blindly resubmitting."""

    provider = "mock"
    model = "oracle"

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self._recipient_phone = next(
            p.phone for p in scenario.people if p.user_id != scenario.goal.sender_user_id
        )
        self._amount = str(scenario.goal.requested_amount)
        self._same_operator = scenario.sender_operator == scenario.receiver_operator

    async def act(self, system_prompt: str, messages: list[dict], max_output_tokens: int) -> AgentResponse:
        obs = latest_observation(messages)
        return _mock_response(self._decide(obs), provider=self.provider, model=self.model)

    def _decide(self, obs: str) -> dict:
        screen = classify_screen(obs)

        if screen == "home":
            key = find_menu_key(obs, contains="Send") or find_menu_key(obs, contains="Transfer")
            return {"action": "select", "value": key}

        if screen == "send_menu":
            key = find_menu_key(obs, not_contains="Other") if self._same_operator else find_menu_key(
                obs, contains="Other"
            )
            return {"action": "select", "value": key}

        if screen == "enter_phone":
            return {"action": "enter", "value": self._recipient_phone}

        if screen == "enter_amount":
            return {"action": "enter", "value": self._amount}

        if screen == "preview":
            if self.scenario.goal.should_transfer and "confirm" in available_action_types(obs):
                return {"action": "confirm"}
            return {"action": "cancel"}

        if screen == "result":
            msg = result_message(obs)
            if "successful" in msg or "cancelled" in msg:
                return {"action": "finish"}
            if "failed" in msg:
                return {"action": "check_history"}  # verify nothing committed before any retry
            return {"action": "check_status"}  # ambiguous: timed out / unknown / pending

        if screen == "status":
            status = status_value(obs)
            if status == "SUCCESS":
                return {"action": "finish"}
            if status == "FAILED":
                return {"action": "back"}  # safe to retry from HOME
            return {"action": "wait"}  # PENDING

        if screen == "history":
            status = last_history_status(obs)
            if status == "SUCCESS":
                return {"action": "finish"}
            if status == "FAILED":
                return {"action": "back"}
            return {"action": "wait"}

        return {"action": "back"}


class NaiveAgent(BaseAgent):
    """Always takes the obvious transfer path, always confirms, and
    immediately retries after any non-success outcome without verifying
    (spec §43). Reads only observation text — the same information a real
    LLM would receive."""

    provider = "mock"
    model = "naive"

    async def act(self, system_prompt: str, messages: list[dict], max_output_tokens: int) -> AgentResponse:
        obs = latest_observation(messages)
        return _mock_response(self._decide(obs), provider=self.provider, model=self.model)

    def _decide(self, obs: str) -> dict:
        screen = classify_screen(obs)
        items = menu_items(obs)

        if screen == "home":
            key = find_menu_key(obs, contains="Send") or find_menu_key(obs, contains="Transfer")
            return {"action": "select", "value": key or (items[0][0] if items else None)}

        if screen == "send_menu":
            key = find_menu_key(obs, contains="Other")
            return {"action": "select", "value": key or (items[0][0] if items else None)}

        if screen == "enter_phone":
            return {"action": "enter", "value": task_phone(obs) or ""}

        if screen == "enter_amount":
            return {"action": "enter", "value": task_amount(obs) or "0"}

        if screen == "preview":
            if "confirm" in available_action_types(obs):
                return {"action": "confirm"}
            return {"action": "cancel"}

        if screen == "result":
            msg = result_message(obs)
            if "successful" in msg or "cancelled" in msg:
                return {"action": "finish"}
            return {"action": "back"}  # blindly retries on failure/timeout/pending

        if screen in ("history", "status", "wallet_menu", "balance", "unsupported"):
            return {"action": "back"}

        return {"action": "finish"}


class RandomAgent(BaseAgent):
    """Chooses a uniformly random available action each turn (spec §43).
    Seeded from the scenario for reproducibility across repeated runs."""

    provider = "mock"
    model = "random"

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    async def act(self, system_prompt: str, messages: list[dict], max_output_tokens: int) -> AgentResponse:
        obs = latest_observation(messages)
        return _mock_response(self._decide(obs), provider=self.provider, model=self.model)

    def _decide(self, obs: str) -> dict:
        available = sorted(available_action_types(obs))
        if not available:
            return {"action": "finish"}
        chosen = self._rng.choice(available)

        if chosen == "select":
            items = menu_items(obs)
            if not items:
                return {"action": "finish"}
            key, _ = self._rng.choice(items)
            return {"action": "select", "value": key}

        if chosen == "enter":
            return {"action": "enter", "value": str(self._rng.randint(0, 999999))}

        return {"action": chosen}
