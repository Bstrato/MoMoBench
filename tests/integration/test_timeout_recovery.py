"""Oracle recovers safely from the hidden-success timeout; Naive duplicates
the payment (spec §83, §86, §114)."""

from decimal import Decimal

import pytest

from momobench.agents.mock_agents import NaiveAgent, OracleAgent
from momobench.envs.ussd.mtn import MTNEnv
from momobench.runner.episode import run_episode
from momobench.scenarios.generator import generate_smoke_suite


def get_scenario(scenario_id: str):
    return next(s for s in generate_smoke_suite() if s.scenario_id == scenario_id)


@pytest.mark.asyncio
async def test_oracle_recovers_from_hidden_success_timeout():
    scenario = get_scenario("smoke_08_hidden_success_timeout")
    env = MTNEnv()
    agent = OracleAgent(scenario)

    result = await run_episode(agent, env, scenario, max_steps=20, max_action_tokens=128)

    assert result.score.safe_success
    assert not result.score.duplicate_payment
    assert result.score.recovery_success is True
    assert result.score.direct_unintended_loss == Decimal("0.00")


@pytest.mark.asyncio
async def test_naive_duplicates_payment_on_hidden_success_timeout():
    scenario = get_scenario("smoke_08_hidden_success_timeout")
    env = MTNEnv()
    agent = NaiveAgent()

    result = await run_episode(agent, env, scenario, max_steps=20, max_action_tokens=128)

    assert not result.score.safe_success
    assert result.score.duplicate_payment
    assert result.score.unsafe_execution
    assert result.score.recovery_success is False
    assert result.score.direct_unintended_loss > Decimal("0.00")
