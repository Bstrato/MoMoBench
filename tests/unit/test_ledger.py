from decimal import Decimal

import pytest

from momobench.core.errors import UnknownTransactionError
from momobench.core.ledger import Ledger
from momobench.core.models import LedgerStatus, Operator, TxType, VisibleStatus


def make_tx(ledger: Ledger, sim_time=0, attempt_no=1):
    return ledger.create_transaction(
        tx_type=TxType.P2P,
        sender_wallet_id="w_a",
        receiver_wallet_id="w_b",
        sender_operator=Operator.MTN,
        receiver_operator=Operator.TELECEL,
        amount=Decimal("100.00"),
        fee=Decimal("1.00"),
        total_debit=Decimal("101.00"),
        sim_time=sim_time,
        scenario_id="s1",
        attempt_no=attempt_no,
    )


def test_create_transaction_starts_created():
    ledger = Ledger()
    tx = make_tx(ledger)
    assert tx.ledger_status == LedgerStatus.CREATED
    assert tx.visible_status == VisibleStatus.CREATED
    assert tx.id == "TX000001"


def test_ids_are_sequential_and_deterministic():
    ledger = Ledger()
    tx1 = make_tx(ledger)
    tx2 = make_tx(ledger)
    assert tx1.id == "TX000001"
    assert tx2.id == "TX000002"


def test_set_status_appends_event_and_updates_transaction():
    ledger = Ledger()
    tx = make_tx(ledger)
    ledger.set_status(
        tx.id,
        ledger_status=LedgerStatus.SUCCESS,
        visible_status=VisibleStatus.SUCCESS,
        committed_at=5,
        sim_time=5,
    )
    updated = ledger.get_transaction(tx.id)
    assert updated.ledger_status == LedgerStatus.SUCCESS
    assert updated.visible_status == VisibleStatus.SUCCESS
    assert updated.committed_at == 5

    events = ledger.events_for_transaction(tx.id)
    event_types = [e.event_type for e in events]
    assert "transaction_created" in event_types
    assert "status_change" in event_types


def test_events_are_append_only_and_ordered():
    ledger = Ledger()
    tx = make_tx(ledger)
    ledger.set_status(tx.id, ledger_status=LedgerStatus.SUCCESS, sim_time=1)
    ledger.set_status(tx.id, ledger_status=LedgerStatus.REVERSED, sim_time=2)
    events = ledger.events()
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)
    assert len(events) == 3  # created + 2 status changes


def test_unknown_transaction_raises():
    ledger = Ledger()
    with pytest.raises(UnknownTransactionError):
        ledger.get_transaction("TX999999")


def test_transactions_for_wallet_includes_sender_and_receiver():
    ledger = Ledger()
    tx = make_tx(ledger)
    assert tx in ledger.transactions_for_wallet("w_a")
    assert tx in ledger.transactions_for_wallet("w_b")
    assert tx not in ledger.transactions_for_wallet("w_c")


def test_outgoing_total_today_only_counts_successful():
    ledger = Ledger()
    tx = make_tx(ledger)
    assert ledger.outgoing_total_today("w_a") == Decimal("0.00")
    ledger.set_status(tx.id, ledger_status=LedgerStatus.SUCCESS, sim_time=1)
    assert ledger.outgoing_total_today("w_a") == Decimal("101.00")
