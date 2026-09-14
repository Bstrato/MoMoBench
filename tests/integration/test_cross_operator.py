"""Integration test: cross-operator routing works identically through a
different provider's USSD skin, and the registry (not the sending
operator's own identity) determines the receiver operator/fee (spec §82,
§2.1 contribution 1)."""

from decimal import Decimal

import pytest

from momobench.actions.schema import AgentAction
from momobench.agents.mock_agents import OracleAgent
from momobench.core.models import LedgerStatus, Operator
from momobench.envs.ussd.mtn import MTNEnv
from momobench.envs.ussd.telecel import TelecelEnv
from momobench.runner.episode import run_episode
from momobench.scenarios.generator import generate_smoke_suite
from tests.integration.test_normal_transfer import find_scenario


def test_mtn_to_telecel_cross_operator_transfer():
    scenario = find_scenario("normal", Operator.MTN, Operator.TELECEL)
    env = MTNEnv()
    env.reset(scenario)

    env.step(AgentAction(action="select", value="1"))  # Send Money
    env.step(AgentAction(action="select", value="2"))  # Other Networks
    env.step(AgentAction(action="enter", value=scenario.people[1].phone))
    r = env.step(AgentAction(action="enter", value=str(scenario.goal.requested_amount)))
    assert "Telecel" in r.observation
    env.step(AgentAction(action="confirm"))
    env.step(AgentAction(action="finish"))

    tx = env.world.ledger.all_transactions()[0]
    assert tx.sender_operator == Operator.MTN
    assert tx.receiver_operator == Operator.TELECEL
    assert tx.fee == Decimal("1.00")  # cross-operator 1% of 100
    assert tx.ledger_status == LedgerStatus.SUCCESS


def test_same_underlying_intent_through_different_provider_ui():
    """Cross-operator generalization requires the same financial intent to
    be reachable through every provider's own USSD skin — here Telecel's UI
    completes an equivalent MTN-bound transfer using Telecel's own menu
    labels, driven through the identical shared MoMoWorld semantics."""
    scenario = find_scenario("normal", Operator.TELECEL, Operator.MTN)
    env = TelecelEnv()
    env.reset(scenario)

    env.step(AgentAction(action="select", value="1"))  # Transfer (Telecel's label)
    env.step(AgentAction(action="select", value="2"))  # Other Network
    env.step(AgentAction(action="enter", value=scenario.people[1].phone))
    env.step(AgentAction(action="enter", value=str(scenario.goal.requested_amount)))
    env.step(AgentAction(action="confirm"))

    tx = env.world.ledger.all_transactions()[0]
    assert tx.sender_operator == Operator.TELECEL
    assert tx.receiver_operator == Operator.MTN


@pytest.mark.asyncio
async def test_ported_number_resolves_to_current_operator_not_prefix_history():
    """spec §86: a number ported away from its original operator must still
    route correctly — Oracle relies on the environment's live resolution,
    never on the number's original/historical operator."""
    scenario = next(s for s in generate_smoke_suite() if s.scenario_id == "smoke_11_ported_number")
    recipient = next(p for p in scenario.people if p.ported)
    assert recipient.original_operator != recipient.operator  # sanity: the trap is real

    env = MTNEnv()
    agent = OracleAgent(scenario)
    result = await run_episode(agent, env, scenario, max_steps=20, max_action_tokens=128)

    assert result.score.safe_success
    tx = env.world.ledger.all_transactions()[0]
    assert tx.receiver_operator == recipient.operator  # current operator, not original_operator
