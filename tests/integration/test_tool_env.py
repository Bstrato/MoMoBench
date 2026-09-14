"""The structured tool interface (spec §100) drives the identical
MoMoWorld as USSD — same scenario, same ledger semantics, different
interaction shape."""

from decimal import Decimal

from momobench.core.models import LedgerStatus, Operator
from momobench.envs.tool.env import ToolEnv
from momobench.envs.tool.schema import ToolAction
from tests.integration.test_normal_transfer import find_scenario


def test_tool_env_completes_normal_transfer():
    scenario = find_scenario("normal", Operator.MTN, Operator.TELECEL)
    env = ToolEnv()
    env.reset(scenario)

    r = env.step(ToolAction(tool="resolve_recipient", arguments={"phone": scenario.people[1].phone}))
    assert "Ama Mensah" in r.observation or scenario.people[1].name in r.observation

    r = env.step(
        ToolAction(
            tool="prepare_transfer",
            arguments={"phone": scenario.people[1].phone, "amount": str(scenario.goal.requested_amount)},
        )
    )
    assert "recipient" in r.observation

    r = env.step(ToolAction(tool="confirm_transfer"))
    assert not r.terminated

    r = env.step(ToolAction(tool="finish"))
    assert r.terminated

    tx = env.world.ledger.all_transactions()[0]
    assert tx.ledger_status == LedgerStatus.SUCCESS
    assert tx.amount == Decimal("100.00")
    assert tx.receiver_operator == Operator.TELECEL


def test_tool_env_blocks_insufficient_funds_without_committing():
    scenario = find_scenario("normal", Operator.MTN, Operator.MTN)
    env = ToolEnv()
    env.reset(scenario)

    r = env.step(
        ToolAction(tool="prepare_transfer", arguments={"phone": scenario.people[1].phone, "amount": "999999"})
    )
    assert "cannot execute" in r.observation.lower()

    r = env.step(ToolAction(tool="confirm_transfer"))
    assert "no executable" in r.observation.lower()
    assert len(env.world.ledger.all_transactions()) == 0
