from decimal import Decimal

import pytest

from momobench.constants import POLICIES_DIR
from momobench.core.errors import InvalidPreviewError
from momobench.core.models import LedgerStatus, Operator, VisibleStatus
from momobench.core.world import create_world
from tests.fixtures.world_helpers import two_party_scenario


def build_world(**kwargs):
    scenario = two_party_scenario(**kwargs)
    return create_world(scenario, POLICIES_DIR), scenario


def test_normal_cross_operator_transfer_commits_exactly_once():
    world, _ = build_world(sender_operator=Operator.MTN, receiver_operator=Operator.TELECEL)

    preview = world.preview_transfer("w_sender", "0200000002", Decimal("100.00"))
    assert preview.can_execute
    assert preview.recipient_name == "Ama Mensah"
    assert preview.receiver_operator == Operator.TELECEL
    assert preview.fee == Decimal("1.00")  # 1% cross-operator fee on 100
    assert preview.total_debit == Decimal("101.00")

    sender_before = world.get_balance("w_sender")
    receiver_before = world.get_balance("w_ama")

    tx = world.commit_transfer(preview)

    assert tx.ledger_status == LedgerStatus.SUCCESS
    assert tx.visible_status == VisibleStatus.SUCCESS
    assert world.get_balance("w_sender") == sender_before - Decimal("101.00")
    assert world.get_balance("w_ama") == receiver_before + Decimal("100.00")
    assert len(world.ledger.all_transactions()) == 1


def test_normal_same_operator_transfer():
    world, _ = build_world(sender_operator=Operator.MTN, receiver_operator=Operator.MTN)
    preview = world.preview_transfer("w_sender", "0200000002", Decimal("100.00"))
    assert preview.fee == Decimal("0.50")  # 0.5% same-operator fee
    tx = world.commit_transfer(preview)
    assert tx.ledger_status == LedgerStatus.SUCCESS


def test_preview_never_mutates_balances():
    world, _ = build_world()
    before_sender = world.get_balance("w_sender")
    before_receiver = world.get_balance("w_ama")
    for _ in range(3):
        world.preview_transfer("w_sender", "0200000002", Decimal("100.00"))
    assert world.get_balance("w_sender") == before_sender
    assert world.get_balance("w_ama") == before_receiver


def test_insufficient_funds_blocks_execution_no_balance_change():
    world, _ = build_world(sender_balance="50.00")
    preview = world.preview_transfer("w_sender", "0200000002", Decimal("100.00"))
    assert not preview.can_execute
    assert preview.blocking_reason == "Insufficient funds."

    before_sender = world.get_balance("w_sender")
    before_receiver = world.get_balance("w_ama")
    with pytest.raises(InvalidPreviewError):
        world.commit_transfer(preview)
    assert world.get_balance("w_sender") == before_sender
    assert world.get_balance("w_ama") == before_receiver
    assert len(world.ledger.all_transactions()) == 0


def test_insufficient_funds_caused_by_fee():
    # balance exactly equals requested amount; fee pushes total_debit over balance
    world, _ = build_world(
        sender_operator=Operator.MTN, receiver_operator=Operator.TELECEL, sender_balance="100.00"
    )
    preview = world.preview_transfer("w_sender", "0200000002", Decimal("100.00"))
    assert not preview.can_execute
    assert preview.blocking_reason == "Insufficient funds."


def test_unknown_recipient_blocks_execution():
    world, _ = build_world()
    preview = world.preview_transfer("w_sender", "0000000000", Decimal("10.00"))
    assert not preview.can_execute
    assert preview.blocking_reason == "No account found for this number."


def test_transaction_limit_violation_blocks_execution():
    world, _ = build_world(sender_balance="99999.00")
    preview = world.preview_transfer("w_sender", "0200000002", Decimal("6000.00"))
    assert not preview.can_execute
    assert "maximum" in preview.blocking_reason.lower()


def test_one_commit_creates_exactly_one_transaction_id():
    world, _ = build_world()
    preview = world.preview_transfer("w_sender", "0200000002", Decimal("50.00"))
    tx = world.commit_transfer(preview)
    assert len(world.ledger.all_transactions()) == 1
    assert world.ledger.get_transaction(tx.id) is not None


def test_conservation_no_money_created():
    world, scenario = build_world(sender_operator=Operator.MTN, receiver_operator=Operator.TELECEL)
    total_before = sum(p.balance for p in scenario.people)

    preview = world.preview_transfer("w_sender", "0200000002", Decimal("100.00"))
    world.commit_transfer(preview)

    snap = world.snapshot()
    total_wallets_after = sum(w.balance for w in snap.wallets)
    # fee leaves user wallets as a system sink (fee revenue), tracked separately.
    assert total_wallets_after + snap.fee_revenue == total_before


def test_reset_restores_exact_initial_scenario_state():
    world, scenario = build_world()
    preview = world.preview_transfer("w_sender", "0200000002", Decimal("50.00"))
    world.commit_transfer(preview)
    assert len(world.ledger.all_transactions()) == 1

    world.reset(scenario)

    assert len(world.ledger.all_transactions()) == 0
    assert world.get_balance("w_sender") == Decimal("500.00")
    assert world.get_balance("w_ama") == Decimal("80.00")
    assert world.clock.now() == 0


def test_registry_authoritative_over_prefix_for_receiver_operator():
    """A number registered under Telecel must resolve to Telecel for fee/
    routing purposes even if its prefix looks like an MTN number."""
    world, _ = build_world(
        sender_operator=Operator.MTN,
        receiver_operator=Operator.TELECEL,
        receiver_phone="0240000009",  # MTN-looking prefix
    )
    preview = world.preview_transfer("w_sender", "0240000009", Decimal("10.00"))
    assert preview.receiver_operator == Operator.TELECEL
