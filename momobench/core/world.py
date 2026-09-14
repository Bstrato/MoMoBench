"""MoMoWorld: the single shared financial engine behind every operator's
USSD interface (spec §24). Owns users, wallets, the number registry, the
ledger, fee/limit policy, the simulated clock, and the episode's failure
plan. No UI/interface strings belong here.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from momobench.core.clock import SimClock
from momobench.core.errors import InvalidPreviewError, UnknownWalletError
from momobench.core.failures import (
    FailurePlan,
    decide_commit_outcome,
    resolution_outcome,
    should_trigger,
)
from momobench.core.fees import FeePolicy
from momobench.core.ledger import Ledger
from momobench.core.limits import LimitPolicy
from momobench.core.models import (
    LedgerStatus,
    Operator,
    RecipientRecord,
    Transaction,
    TransactionPreview,
    TxType,
    User,
    Wallet,
    WalletSnapshot,
    WorldSnapshot,
)
from momobench.core.registry import NumberRegistry
from momobench.utils.money import ZERO, money


class MoMoWorld:
    def __init__(self, fee_policy: FeePolicy, limit_policy: LimitPolicy) -> None:
        self.fee_policy = fee_policy
        self.limit_policy = limit_policy

        self.clock = SimClock()
        self.ledger = Ledger()
        self.registry = NumberRegistry()

        self._users: dict[str, User] = {}
        self._wallets: dict[str, Wallet] = {}
        self._fee_revenue: Decimal = ZERO
        self._attempt_no = 0
        self._failure_plan = FailurePlan()

        self.scenario_id: str | None = None
        self.initial_snapshot: WorldSnapshot | None = None

    # -- setup -----------------------------------------------------------

    def reset(self, scenario) -> None:
        """Reinitialize this world for a fresh episode. Every scenario run
        must get a fresh, isolated ``MoMoWorld`` instance (spec §5.7) — this
        method does not need to be called on a shared instance across
        episodes, but is provided so callers may reuse one instance across
        sequential (never concurrent) episodes if they choose to.
        """
        self.clock = SimClock()
        self.ledger = Ledger()
        self.registry = NumberRegistry()
        self._users = {}
        self._wallets = {}
        self._fee_revenue = ZERO
        self._attempt_no = 0

        self.scenario_id = scenario.scenario_id
        self._failure_plan = FailurePlan(
            mode=scenario.failure.mode,
            trigger_attempt=scenario.failure.trigger_attempt,
            resolve_after_steps=scenario.failure.resolve_after_steps,
        )

        for person in scenario.people:
            user = User(id=person.user_id, name=person.name, phone=person.phone)
            wallet_id = f"w_{person.user_id}"
            wallet = Wallet(
                id=wallet_id,
                user_id=person.user_id,
                operator=person.operator,
                balance=money(person.balance),
            )
            self._users[user.id] = user
            self._wallets[wallet.id] = wallet
            self.registry.register_number(
                phone=person.phone,
                user_id=user.id,
                wallet_id=wallet.id,
                operator=person.operator,
                original_operator=person.original_operator,
                ported=person.ported,
            )

        self.initial_snapshot = self.snapshot()

    def add_user(self, user: User) -> None:
        self._users[user.id] = user

    def add_wallet(self, wallet: Wallet) -> None:
        self._wallets[wallet.id] = wallet

    # -- queries -----------------------------------------------------------

    def get_wallet(self, wallet_id: str) -> Wallet:
        wallet = self._wallets.get(wallet_id)
        if wallet is None:
            raise UnknownWalletError(f"no such wallet: {wallet_id!r}")
        return wallet

    def get_balance(self, wallet_id: str) -> Decimal:
        return self.get_wallet(wallet_id).balance

    def resolve_recipient(self, phone: str) -> RecipientRecord | None:
        """Resolve a phone number to what the environment is entitled to
        show about it. Returns ``None`` if the number is not registered
        (i.e. no such account exists) rather than raising, since a wrong
        number is ordinary benchmark behavior, not a programmatic error.

        The returned ``operator`` is always the registry's *current*
        operator — a phone-number prefix is never authoritative (spec §14).
        """
        record = self.registry.try_resolve_number(phone)
        if record is None:
            return None
        user = self._users[record.user_id]
        return RecipientRecord(
            user_id=user.id,
            wallet_id=record.wallet_id,
            name=user.name,
            phone=phone,
            operator=record.current_operator,
        )

    def port_number(self, phone: str, new_operator: Operator) -> None:
        record = self.registry.port_number(phone, new_operator)
        wallet = self.get_wallet(record.wallet_id)
        wallet.operator = new_operator

    # -- transfer: preview -> commit --------------------------------------

    def preview_transfer(
        self, sender_wallet_id: str, recipient_phone: str, amount: Decimal
    ) -> TransactionPreview:
        """Compute a transfer preview. Never mutates balances."""
        amount = money(amount)
        sender = self.get_wallet(sender_wallet_id)
        recipient = self.resolve_recipient(recipient_phone)

        if recipient is None:
            return TransactionPreview(
                sender_wallet_id=sender_wallet_id,
                receiver_wallet_id="",
                recipient_name="",
                recipient_phone=recipient_phone,
                sender_operator=sender.operator,
                receiver_operator=sender.operator,
                amount=amount,
                fee=ZERO,
                total_debit=amount,
                can_execute=False,
                blocking_reason="No account found for this number.",
            )

        receiver_wallet = self.get_wallet(recipient.wallet_id)
        fee = self.fee_policy.calculate(sender.operator, recipient.operator, amount)
        total_debit = money(amount + fee)

        blocking_reason: str | None = None
        if not sender.active:
            blocking_reason = "Sender wallet is inactive."
        elif not receiver_wallet.active:
            blocking_reason = "Recipient wallet is inactive."
        elif receiver_wallet.id == sender.id:
            blocking_reason = "Cannot send money to your own wallet."
        else:
            violation = self.limit_policy.check(
                amount, prior_outgoing_today=self.ledger.outgoing_total_today(sender.id)
            )
            if violation is not None:
                blocking_reason = violation.message
            elif sender.balance < total_debit:
                blocking_reason = "Insufficient funds."

        return TransactionPreview(
            sender_wallet_id=sender.id,
            receiver_wallet_id=receiver_wallet.id,
            recipient_name=recipient.name,
            recipient_phone=recipient_phone,
            sender_operator=sender.operator,
            receiver_operator=recipient.operator,
            amount=amount,
            fee=fee,
            total_debit=total_debit,
            can_execute=blocking_reason is None,
            blocking_reason=blocking_reason,
        )

    def commit_transfer(self, preview: TransactionPreview) -> Transaction:
        """Atomically commit a previously-shown preview. Order follows spec
        §20: revalidate, verify wallets/amount/fee/limits/balance, create
        the transaction, apply failure-injection rules, move funds only if
        the failure semantics require it, append immutable ledger events.
        """
        sim_time = self.clock.now()

        fresh = self.preview_transfer(preview.sender_wallet_id, preview.recipient_phone, preview.amount)
        if not fresh.can_execute:
            raise InvalidPreviewError(
                f"preview is no longer executable: {fresh.blocking_reason}"
            )

        self._attempt_no += 1
        attempt_no = self._attempt_no

        tx = self.ledger.create_transaction(
            tx_type=TxType.P2P,
            sender_wallet_id=fresh.sender_wallet_id,
            receiver_wallet_id=fresh.receiver_wallet_id,
            sender_operator=fresh.sender_operator,
            receiver_operator=fresh.receiver_operator,
            amount=fresh.amount,
            fee=fresh.fee,
            total_debit=fresh.total_debit,
            sim_time=sim_time,
            scenario_id=self.scenario_id or "",
            attempt_no=attempt_no,
        )

        outcome = decide_commit_outcome(self._failure_plan, attempt_no)
        if should_trigger(self._failure_plan, attempt_no):
            tx.failure_mode = self._failure_plan.mode

        if outcome.apply_funds_now:
            self._move_funds(tx)

        if outcome.resolve_after_steps is not None:
            tx.resolve_at = sim_time + outcome.resolve_after_steps

        self.ledger.set_status(
            tx.id,
            ledger_status=outcome.ledger_status,
            visible_status=outcome.visible_status,
            committed_at=sim_time if outcome.ledger_status == LedgerStatus.SUCCESS else None,
            sim_time=sim_time,
            event_type="commit_attempt",
            event_data={"attempt_no": attempt_no, "message": outcome.message},
        )

        return self.ledger.get_transaction(tx.id)

    def _move_funds(self, tx: Transaction) -> None:
        sender = self.get_wallet(tx.sender_wallet_id)
        receiver = self.get_wallet(tx.receiver_wallet_id)
        sender.balance = money(sender.balance - tx.total_debit)
        receiver.balance = money(receiver.balance + tx.amount)
        self._fee_revenue = money(self._fee_revenue + tx.fee)

    # -- simulated time / pending resolution -------------------------------

    def advance_time(self, n: int = 1) -> int:
        t = self.clock.tick(n)
        self._resolve_due_pending()
        return t

    def _resolve_due_pending(self) -> None:
        now = self.clock.now()
        for tx in self.ledger.all_transactions():
            if (
                tx.ledger_status == LedgerStatus.PENDING
                and tx.resolve_at is not None
                and now >= tx.resolve_at
            ):
                resolution = resolution_outcome(self._failure_plan)
                if resolution.apply_funds_now:
                    self._move_funds(tx)
                self.ledger.set_status(
                    tx.id,
                    ledger_status=resolution.ledger_status,
                    visible_status=resolution.visible_status,
                    committed_at=now if resolution.ledger_status == LedgerStatus.SUCCESS else None,
                    sim_time=now,
                    event_type="pending_resolved",
                    event_data={"message": resolution.message},
                )

    # -- history / status ---------------------------------------------------

    def transaction_history(self, wallet_id: str) -> tuple[Transaction, ...]:
        self._resolve_due_pending()
        return tuple(
            sorted(self.ledger.transactions_for_wallet(wallet_id), key=lambda t: (t.created_at, t.id))
        )

    def transaction_status(self, tx_id: str) -> Transaction:
        self._resolve_due_pending()
        return self.ledger.get_transaction(tx_id)

    # -- snapshot -------------------------------------------------------

    def snapshot(self) -> WorldSnapshot:
        return WorldSnapshot(
            sim_time=self.clock.now(),
            wallets=tuple(
                WalletSnapshot(
                    id=w.id, user_id=w.user_id, operator=w.operator, balance=w.balance, active=w.active
                )
                for w in self._wallets.values()
            ),
            transaction_count=len(self.ledger.all_transactions()),
            fee_revenue=self._fee_revenue,
        )


def create_world(scenario, policies_dir: str | Path) -> MoMoWorld:
    """Factory: build a fresh, isolated ``MoMoWorld`` for ``scenario``,
    loading the fee/limit policies it references by their ``policy_id``
    (never live-fetched — spec §117)."""
    fee_policy = FeePolicy.from_policy_id(scenario.fee_policy_id, Path(policies_dir))
    limit_policy = LimitPolicy.from_policy_id(scenario.limits_policy_id, Path(policies_dir))
    world = MoMoWorld(fee_policy=fee_policy, limit_policy=limit_policy)
    world.reset(scenario)
    return world
