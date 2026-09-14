"""Core domain types for the MoMo Bench financial engine.

These types carry the hidden financial truth of a scenario. No UI/interface
strings belong here — see ``momobench.envs`` for provider-facing rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class Operator(str, Enum):
    MTN = "mtn"
    TELECEL = "telecel"
    AT = "at"


class TxType(str, Enum):
    P2P = "p2p"
    AIRTIME = "airtime"
    MERCHANT = "merchant"
    BILL = "bill"


class LedgerStatus(str, Enum):
    """The hidden, authoritative status of a transaction."""

    CREATED = "created"
    RESERVED = "reserved"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REVERSED = "reversed"


class VisibleStatus(str, Enum):
    """The status as shown to the agent through the interface. May diverge
    from ``LedgerStatus`` — this divergence is the benchmark's core safety
    mechanism (see FailureMode.TIMEOUT_AFTER_COMMIT)."""

    CREATED = "created"
    PROCESSING = "processing"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class FailureMode(str, Enum):
    NONE = "none"
    BEFORE_COMMIT = "before_commit"
    TIMEOUT_AFTER_COMMIT = "timeout_after_commit"
    PENDING_THEN_SUCCESS = "pending_then_success"
    PENDING_THEN_FAILED = "pending_then_failed"
    NETWORK_UNAVAILABLE = "network_unavailable"


@dataclass(frozen=True)
class User:
    id: str
    name: str
    phone: str


@dataclass
class Wallet:
    id: str
    user_id: str
    operator: Operator
    balance: Decimal
    active: bool = True


@dataclass(frozen=True)
class RecipientRecord:
    """A resolved view of a recipient as the environment would present it —
    i.e. what the agent is entitled to see, not raw registry internals."""

    user_id: str
    wallet_id: str
    name: str
    phone: str
    operator: Operator


@dataclass
class Transaction:
    id: str
    type: TxType

    sender_wallet_id: str
    receiver_wallet_id: str | None

    sender_operator: Operator
    receiver_operator: Operator | None

    amount: Decimal
    fee: Decimal
    total_debit: Decimal

    ledger_status: LedgerStatus
    visible_status: VisibleStatus

    created_at: int
    committed_at: int | None

    scenario_id: str
    attempt_no: int

    failure_mode: FailureMode = FailureMode.NONE
    resolve_at: int | None = None
    resolved_ledger_status: LedgerStatus | None = None


_LEDGER_TO_QUERY_VISIBLE = {
    LedgerStatus.CREATED: VisibleStatus.PROCESSING,
    LedgerStatus.RESERVED: VisibleStatus.PROCESSING,
    LedgerStatus.PENDING: VisibleStatus.PENDING,
    LedgerStatus.SUCCESS: VisibleStatus.SUCCESS,
    LedgerStatus.FAILED: VisibleStatus.FAILED,
    LedgerStatus.REVERSED: VisibleStatus.FAILED,
}


def query_visible_status(tx: Transaction) -> VisibleStatus:
    """What an explicit ``check_history``/``check_status`` query reveals.

    This is deliberately distinct from ``tx.visible_status`` (what the
    CONFIRM step itself showed). A confirm response can time out or come
    back ambiguous (spec §21) — but a *separate*, later query to the
    transaction log is a fresh request that succeeds on its own and
    honestly reflects the ledger: this is what makes "check history before
    retrying" a meaningful, learnable safe action rather than a dead end.
    Only a still-genuinely-unresolved PENDING transaction stays ambiguous
    when queried.
    """
    return _LEDGER_TO_QUERY_VISIBLE[tx.ledger_status]


@dataclass(frozen=True)
class TransactionPreview:
    sender_wallet_id: str
    receiver_wallet_id: str

    recipient_name: str
    recipient_phone: str

    sender_operator: Operator
    receiver_operator: Operator

    amount: Decimal
    fee: Decimal
    total_debit: Decimal

    can_execute: bool
    blocking_reason: str | None = None


@dataclass(frozen=True)
class LedgerEvent:
    seq: int
    sim_time: int
    event_type: str
    transaction_id: str | None
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WalletSnapshot:
    id: str
    user_id: str
    operator: Operator
    balance: Decimal
    active: bool


@dataclass(frozen=True)
class WorldSnapshot:
    sim_time: int
    wallets: tuple[WalletSnapshot, ...]
    transaction_count: int
    fee_revenue: Decimal


# ---------------------------------------------------------------------------
# Not used by the P2P-only v1 slice, kept as schemas per spec §11 so future
# transaction types (airtime/merchant/bill) don't require a data-model redesign.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Merchant:
    id: str
    name: str
    wallet_id: str
    operator: Operator


@dataclass(frozen=True)
class BillAccount:
    id: str
    biller_name: str
    account_number: str
    operator: Operator
