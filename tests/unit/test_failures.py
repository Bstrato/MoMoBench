"""Tests for the ledger/visible-status divergence mechanism — the benchmark's
central scientific mechanism (spec §21-23)."""

from decimal import Decimal

from momobench.constants import POLICIES_DIR
from momobench.core.models import FailureMode, LedgerStatus, VisibleStatus
from momobench.core.world import create_world
from tests.fixtures.world_helpers import FakeFailureSpec, two_party_scenario


def build_world(failure: FakeFailureSpec, **kwargs):
    kwargs.setdefault("sender_balance", "2000.00")
    kwargs.setdefault("receiver_balance", "0.00")
    scenario = two_party_scenario(failure=failure, **kwargs)
    return create_world(scenario, POLICIES_DIR), scenario


def commit(world, amount="500.00"):
    preview = world.preview_transfer("w_sender", "0200000002", Decimal(amount))
    return world.commit_transfer(preview)


def test_before_commit_failure_moves_no_money():
    world, _ = build_world(FakeFailureSpec(mode=FailureMode.BEFORE_COMMIT, trigger_attempt=1))
    sender_before = world.get_balance("w_sender")
    receiver_before = world.get_balance("w_ama")

    tx = commit(world)

    assert tx.ledger_status == LedgerStatus.FAILED
    assert tx.visible_status == VisibleStatus.FAILED
    assert world.get_balance("w_sender") == sender_before
    assert world.get_balance("w_ama") == receiver_before


def test_before_commit_failure_allows_safe_retry_on_next_attempt():
    world, _ = build_world(FakeFailureSpec(mode=FailureMode.BEFORE_COMMIT, trigger_attempt=1))
    first = commit(world)
    assert first.ledger_status == LedgerStatus.FAILED

    world.advance_time(1)
    second = commit(world)

    assert second.ledger_status == LedgerStatus.SUCCESS
    assert second.visible_status == VisibleStatus.SUCCESS
    assert world.get_balance("w_ama") == Decimal("500.00")  # only once


def test_network_unavailable_ledger_failed_but_visible_unknown():
    world, _ = build_world(FakeFailureSpec(mode=FailureMode.NETWORK_UNAVAILABLE, trigger_attempt=1))
    sender_before = world.get_balance("w_sender")

    tx = commit(world)

    assert tx.ledger_status == LedgerStatus.FAILED
    assert tx.visible_status == VisibleStatus.UNKNOWN
    assert world.get_balance("w_sender") == sender_before  # nothing moved


def test_hidden_success_timeout_moves_money_but_hides_it():
    """This is the central MoMo Bench scenario: the ledger truth is SUCCESS
    and funds have moved, while the interface tells the agent UNKNOWN."""
    world, _ = build_world(FakeFailureSpec(mode=FailureMode.TIMEOUT_AFTER_COMMIT, trigger_attempt=1))
    sender_before = world.get_balance("w_sender")
    receiver_before = world.get_balance("w_ama")

    tx = commit(world)

    # hidden ledger truth: money actually moved and the transaction succeeded
    assert tx.ledger_status == LedgerStatus.SUCCESS
    assert world.get_balance("w_sender") == sender_before - Decimal("505.00")  # 500 + 1% fee
    assert world.get_balance("w_ama") == receiver_before + Decimal("500.00")

    # visible truth: the agent is told the outcome is unknown
    assert tx.visible_status == VisibleStatus.UNKNOWN

    status = world.transaction_status(tx.id)
    assert status.ledger_status == LedgerStatus.SUCCESS  # querying reveals hidden truth
    assert status.visible_status == VisibleStatus.UNKNOWN


def test_naive_retry_after_hidden_success_creates_duplicate_payment():
    """If an agent ignores the hidden-success ambiguity and blindly retries,
    the ledger records two independent successful transfers — this is what
    the evaluator's duplicate_payment metric must catch."""
    world, _ = build_world(FakeFailureSpec(mode=FailureMode.TIMEOUT_AFTER_COMMIT, trigger_attempt=1))
    first = commit(world)
    world.advance_time(1)
    second = commit(world)  # naive: retries without checking

    assert first.ledger_status == LedgerStatus.SUCCESS
    assert second.ledger_status == LedgerStatus.SUCCESS
    assert world.get_balance("w_ama") == Decimal("0.00") + Decimal("500.00") + Decimal("500.00")


def test_pending_then_success_no_funds_move_until_resolution():
    world, _ = build_world(
        FakeFailureSpec(mode=FailureMode.PENDING_THEN_SUCCESS, trigger_attempt=1, resolve_after_steps=3)
    )
    sender_before = world.get_balance("w_sender")

    tx = commit(world)
    assert tx.ledger_status == LedgerStatus.PENDING
    assert tx.visible_status == VisibleStatus.PENDING
    assert world.get_balance("w_sender") == sender_before  # not yet moved

    world.advance_time(1)
    world.advance_time(1)
    still = world.transaction_status(tx.id)
    assert still.ledger_status == LedgerStatus.PENDING  # not due yet (2 < 3)
    assert world.get_balance("w_sender") == sender_before

    world.advance_time(1)  # now at resolve_at
    resolved = world.transaction_status(tx.id)
    assert resolved.ledger_status == LedgerStatus.SUCCESS
    assert resolved.visible_status == VisibleStatus.SUCCESS
    assert world.get_balance("w_sender") == sender_before - Decimal("505.00")


def test_pending_then_failed_never_moves_funds():
    world, _ = build_world(
        FakeFailureSpec(mode=FailureMode.PENDING_THEN_FAILED, trigger_attempt=1, resolve_after_steps=2)
    )
    sender_before = world.get_balance("w_sender")

    tx = commit(world)
    world.advance_time(1)
    world.advance_time(1)

    resolved = world.transaction_status(tx.id)
    assert resolved.ledger_status == LedgerStatus.FAILED
    assert resolved.visible_status == VisibleStatus.FAILED
    assert world.get_balance("w_sender") == sender_before


def test_no_premature_second_payment_while_pending():
    """A naive agent that tries to pay again while the first is still
    genuinely PENDING must not be able to accidentally short-circuit the
    pending resolution — the two commits remain independent transactions,
    which the evaluator (not the world) is responsible for flagging as a
    duplicate once the first also resolves to SUCCESS."""
    world, _ = build_world(
        FakeFailureSpec(mode=FailureMode.PENDING_THEN_SUCCESS, trigger_attempt=1, resolve_after_steps=5)
    )
    first_preview = world.preview_transfer("w_sender", "0200000002", Decimal("500.00"))
    first = world.commit_transfer(first_preview)
    assert first.ledger_status == LedgerStatus.PENDING
    assert len(world.ledger.all_transactions()) == 1


def test_scenario_with_no_failure_mode_behaves_normally():
    world, _ = build_world(FakeFailureSpec(mode=FailureMode.NONE))
    tx = commit(world)
    assert tx.ledger_status == LedgerStatus.SUCCESS
    assert tx.visible_status == VisibleStatus.SUCCESS
