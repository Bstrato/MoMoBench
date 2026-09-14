"""Single-episode execution (spec §51). This is the one place the agent
loop, action parser, environment, and scorer are wired together — every
agent (mock or real provider) goes through exactly this loop, so behavior
differences are never explained by different plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from momobench.actions.parser import parse_action
from momobench.agents.base import BaseAgent
from momobench.agents.prompts import COMMON_SYSTEM_PROMPT
from momobench.envs.base import BaseMoMoEnv
from momobench.evaluation.scorer import EpisodeScore, score
from momobench.scenarios.schema import Scenario


def invalid_action_observation(previous_observation: str, error: str) -> str:
    """The next observation shown after a parser failure: state does not
    change, only the error is surfaced (spec §27)."""
    marker = "\n\n" + error
    if previous_observation.endswith(marker):
        return previous_observation  # avoid stacking duplicate error text on repeated failures
    return previous_observation + marker


@dataclass
class EpisodeResult:
    scenario_id: str
    provider: str
    model: str

    score: EpisodeScore
    transcript: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)

    terminated: bool = False
    truncated: bool = False

    total_turns: int = 0
    format_errors: int = 0

    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms_total: float = 0.0


async def run_episode(
    agent: BaseAgent,
    env: BaseMoMoEnv,
    scenario: Scenario,
    *,
    max_steps: int,
    max_action_tokens: int,
    system_prompt: str = COMMON_SYSTEM_PROMPT,
    parse_fn=parse_action,
) -> EpisodeResult:
    obs = env.reset(scenario)

    transcript: list[dict] = []
    trace: list[dict] = []
    format_errors = 0
    input_tokens_total = 0
    output_tokens_total = 0
    latency_ms_total = 0.0
    have_token_counts = False

    terminated = False
    truncated = False
    turns_used = 0

    for turn in range(max_steps):
        turns_used = turn + 1
        req_messages = transcript + [{"role": "user", "content": obs}]

        rsp = await agent.act(
            system_prompt=system_prompt, messages=req_messages, max_output_tokens=max_action_tokens
        )

        if rsp.input_tokens is not None:
            input_tokens_total += rsp.input_tokens
            have_token_counts = True
        if rsp.output_tokens is not None:
            output_tokens_total += rsp.output_tokens
            have_token_counts = True
        latency_ms_total += rsp.latency_ms

        parsed = parse_fn(rsp.text)

        transcript.append({"role": "user", "content": obs})
        transcript.append({"role": "assistant", "content": rsp.text})

        if not parsed.ok:
            format_errors += 1
            trace.append({"event_type": "action_parse_error", "error": parsed.error, "raw_text": rsp.text})
            obs = invalid_action_observation(obs, parsed.error)
            continue

        # Interface-agnostic: AgentAction (USSD, action/value) and ToolAction
        # (tool/arguments) are both pydantic models but carry different
        # fields, so this must not assume the USSD shape.
        trace.append({"event_type": "agent_action", **parsed.action.model_dump()})

        step_result = env.step(parsed.action)
        trace.append({"event_type": "env_transition", **step_result.info})
        obs = step_result.observation

        if step_result.terminated or step_result.truncated:
            terminated = step_result.terminated
            truncated = step_result.truncated
            break
    else:
        terminated = False
        truncated = True

    ep_score = score(
        scenario=scenario,
        ledger=env.world.ledger,
        terminated=terminated,
        truncated=truncated,
        trace=trace,
        steps=turns_used,
        format_errors=format_errors,
    )

    return EpisodeResult(
        scenario_id=scenario.scenario_id,
        provider=agent.provider,
        model=agent.model,
        score=ep_score,
        transcript=transcript,
        trace=trace,
        terminated=terminated,
        truncated=truncated,
        total_turns=turns_used,
        format_errors=format_errors,
        input_tokens=input_tokens_total if have_token_counts else None,
        output_tokens=output_tokens_total if have_token_counts else None,
        latency_ms_total=latency_ms_total,
    )
