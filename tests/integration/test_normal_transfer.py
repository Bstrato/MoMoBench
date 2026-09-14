"""Integration test: a hand-driven agent walks the MTN USSD interface
through a same-operator transfer end-to-end (spec §82, minimum vertical
slice)."""

from decimal import Decimal

from momobench.actions.schema import AgentAction
from momobench.core.models import LedgerStatus, Operator, VisibleStatus
from momobench.envs.ussd.mtn import MTNEnv
from momobench.scenarios.generator import generate_grid


def find_scenario(family: str, sender: Operator, receiver: Operator):
    for s in generate_grid(seeds_per_combo=1, families=[family]):
        if s.sender_operator == sender and s.receiver_operator == receiver:
            return s
    raise AssertionError("scenario not found")


def test_normal_same_operator_transfer_end_to_end():
    scenario = find_scenario("normal", Operator.MTN, Operator.MTN)
    env = MTNEnv()
    obs = env.reset(scenario)
    assert "[TASK]" in obs
    assert scenario.instruction in obs

    r = env.step(AgentAction(action="select", value="1"))  # Send Money
    assert not r.terminated
    r = env.step(AgentAction(action="select", value="1"))  # MTN Wallet (same-operator)
    r = env.step(AgentAction(action="enter", value=scenario.people[1].phone))
    assert "AMA" in r.observation.upper() or scenario.people[1].name.upper() in r.observation.upper()
    r = env.step(AgentAction(action="enter", value=str(scenario.goal.requested_amount)))
    assert "Confirm Transaction" in r.observation
    r = env.step(AgentAction(action="confirm"))
    assert "successful" in r.observation.lower()
    r = env.step(AgentAction(action="finish"))
    assert r.terminated

    txs = env.world.ledger.all_transactions()
    assert len(txs) == 1
    tx = txs[0]
    assert tx.ledger_status == LedgerStatus.SUCCESS
    assert tx.visible_status == VisibleStatus.SUCCESS
    assert tx.amount == Decimal("100.00")
