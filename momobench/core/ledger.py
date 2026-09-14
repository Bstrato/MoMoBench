"""The ledger: the sole source of financial truth.

Transactions may transition status over time (e.g. PENDING -> SUCCESS on
deterministic resolution), but every mutation appends an immutable
``LedgerEvent`` — the audit trail itself is append-only even though the
current-state view (``Transaction``) is a mutable projection of it (spec
§5.6, §15).
"""

from __future__ import annotations

from decimal import Decimal

from momobench.core.errors import UnknownTransactionError
from momobench.core.models import (
    LedgerEvent,
    LedgerStatus,
    Operator,
    Transaction,
    TxType,
    VisibleStatus,
)
from momobench.utils.ids import SequentialIdFactory
from momobench.utils.money import ZERO


class Ledger:
    def __init__(self) -> None:
        self._tx_id_factory = SequentialIdFactory(prefix="TX", width=6)
        self._transactions: dict[str, Transaction] = {}
        self._events: list[LedgerEvent] = []
        self._event_seq = 0

    # -- events ---------------------------------------------------------

    def _append_event(self, *, sim_time: int, event_type: str, transaction_id: str | None, data: dict) -> LedgerEvent:
        self._event_seq += 1
        event = LedgerEvent(
            seq=self._event_seq,
            sim_time=sim_time,
            event_type=event_type,
            transaction_id=transaction_id,
            data=dict(data),
        )
        self._events.append(event)
        return event

    def events(self) -> tuple[LedgerEvent, ...]:
        return tuple(self._events)

    def events_for_transaction(self, tx_id: str) -> tuple[LedgerEvent, ...]:
        return tuple(e for e in self._events if e.transaction_id == tx_id)

    # -- transaction lifecycle ------------------------------------------

    def create_transaction(
        self,
        *,
        tx_type: TxType,
        sender_wallet_id: str,
        receiver_wallet_id: str | None,
        sender_operator: Operator,
        receiver_operator: Operator | None,
        amount: Decimal,
        fee: Decimal,
        total_debit: Decimal,
        sim_time: int,
        scenario_id: str,
        attempt_no: int,
    ) -> Transaction:
        tx = Transaction(
            id=self._tx_id_factory.next(),
            type=tx_type,
            sender_wallet_id=sender_wallet_id,
            receiver_wallet_id=receiver_wallet_id,
            sender_operator=sender_operator,
            receiver_operator=receiver_operator,
            amount=amount,
            fee=fee,
            total_debit=total_debit,
            ledger_status=LedgerStatus.CREATED,
            visible_status=VisibleStatus.CREATED,
            created_at=sim_time,
            committed_at=None,
            scenario_id=scenario_id,
            attempt_no=attempt_no,
        )
        self._transactions[tx.id] = tx
        self._append_event(
            sim_time=sim_time,
            event_type="transaction_created",
            transaction_id=tx.id,
            data={"amount": str(amount), "fee": str(fee)},
        )
        return tx

    def set_status(
        self,
        tx_id: str,
        *,
        ledger_status: LedgerStatus | None = None,
        visible_status: VisibleStatus | None = None,
        committed_at: int | None = None,
        sim_time: int,
        event_type: str = "status_change",
        event_data: dict | None = None,
    ) -> Transaction:
        tx = self.get_transaction(tx_id)
        if ledger_status is not None:
            tx.ledger_status = ledger_status
        if visible_status is not None:
            tx.visible_status = visible_status
        if committed_at is not None:
            tx.committed_at = committed_at
        self._append_event(
            sim_time=sim_time,
            event_type=event_type,
            transaction_id=tx_id,
            data={
                "ledger_status": tx.ledger_status.value,
                "visible_status": tx.visible_status.value,
                **(event_data or {}),
            },
        )
        return tx

    def get_transaction(self, tx_id: str) -> Transaction:
        tx = self._transactions.get(tx_id)
        if tx is None:
            raise UnknownTransactionError(f"no such transaction: {tx_id!r}")
        return tx

    def transactions_for_wallet(self, wallet_id: str) -> tuple[Transaction, ...]:
        return tuple(
            tx
            for tx in self._transactions.values()
            if tx.sender_wallet_id == wallet_id or tx.receiver_wallet_id == wallet_id
        )

    def all_transactions(self) -> tuple[Transaction, ...]:
        return tuple(self._transactions.values())

    def successful_outgoing(self, wallet_id: str) -> tuple[Transaction, ...]:
        return tuple(
            tx
            for tx in self._transactions.values()
            if tx.sender_wallet_id == wallet_id and tx.ledger_status == LedgerStatus.SUCCESS
        )

    def outgoing_total_today(self, wallet_id: str) -> Decimal:
        """Sum of committed (SUCCESS) outgoing total_debit for a wallet.

        The benchmark uses a single simulated "day" per episode, so this is
        simply the sum over the episode so far.
        """
        total = ZERO
        for tx in self.successful_outgoing(wallet_id):
            total += tx.total_debit
        return total
