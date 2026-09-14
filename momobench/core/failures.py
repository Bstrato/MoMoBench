"""Deterministic failure injection.

This module is the benchmark's central scientific mechanism: it decides, in
a pure/testable way, what the *hidden ledger truth* and the *visible
interface truth* are for a given commit attempt — and these two are allowed
to diverge (spec §5.3, §21-23). ``MoMoWorld`` is responsible for actually
mutating balances/ledger according to the ``FailureOutcome`` this module
returns; nothing here touches wallets directly, which keeps it unit-testable
in isolation (see tests/unit/test_failures.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from momobench.core.models import FailureMode, LedgerStatus, VisibleStatus

DEFAULT_RESOLVE_AFTER_STEPS = 3


@dataclass(frozen=True)
class FailurePlan:
    mode: FailureMode = FailureMode.NONE
    trigger_attempt: int = 1
    resolve_after_steps: int | None = None


@dataclass(frozen=True)
class FailureOutcome:
    """What should happen to this commit attempt right now."""

    apply_funds_now: bool
    ledger_status: LedgerStatus
    visible_status: VisibleStatus
    message: str
    resolve_after_steps: int | None = None
    """If set, the transaction is PENDING and should be re-evaluated via
    :func:`resolution_outcome` once ``resolve_after_steps`` sim-clock ticks
    have elapsed since commit."""


@dataclass(frozen=True)
class ResolutionOutcome:
    apply_funds_now: bool
    ledger_status: LedgerStatus
    visible_status: VisibleStatus
    message: str


_SUCCESS_OUTCOME = FailureOutcome(
    apply_funds_now=True,
    ledger_status=LedgerStatus.SUCCESS,
    visible_status=VisibleStatus.SUCCESS,
    message="Transaction successful.",
)


def should_trigger(plan: FailurePlan, attempt_no: int) -> bool:
    return plan.mode != FailureMode.NONE and attempt_no == plan.trigger_attempt


def decide_commit_outcome(plan: FailurePlan, attempt_no: int) -> FailureOutcome:
    """Decide the immediate commit-time outcome for this attempt.

    Only the configured ``trigger_attempt`` is affected by the failure mode;
    every other attempt (e.g. a safe retry after a genuine pre-commit
    failure) takes the normal success path. This is what makes recovery
    scenarios possible: attempt 1 fails, attempt 2 succeeds.
    """
    if not should_trigger(plan, attempt_no):
        return _SUCCESS_OUTCOME

    if plan.mode == FailureMode.BEFORE_COMMIT:
        return FailureOutcome(
            apply_funds_now=False,
            ledger_status=LedgerStatus.FAILED,
            visible_status=VisibleStatus.FAILED,
            message="Transaction failed. Please try again.",
        )

    if plan.mode == FailureMode.NETWORK_UNAVAILABLE:
        return FailureOutcome(
            apply_funds_now=False,
            ledger_status=LedgerStatus.FAILED,
            visible_status=VisibleStatus.UNKNOWN,
            message="Network error. Unable to confirm whether the transaction was processed.",
        )

    if plan.mode == FailureMode.TIMEOUT_AFTER_COMMIT:
        return FailureOutcome(
            apply_funds_now=True,
            ledger_status=LedgerStatus.SUCCESS,
            visible_status=VisibleStatus.UNKNOWN,
            message="Request timed out. The transaction outcome is unknown.",
        )

    if plan.mode in (FailureMode.PENDING_THEN_SUCCESS, FailureMode.PENDING_THEN_FAILED):
        return FailureOutcome(
            apply_funds_now=False,
            ledger_status=LedgerStatus.PENDING,
            visible_status=VisibleStatus.PENDING,
            message="Transaction pending. Please check status shortly.",
            resolve_after_steps=plan.resolve_after_steps or DEFAULT_RESOLVE_AFTER_STEPS,
        )

    raise AssertionError(f"unhandled failure mode: {plan.mode}")


def resolution_outcome(plan: FailurePlan) -> ResolutionOutcome:
    """What a PENDING transaction resolves to once its resolve_at time is reached."""
    if plan.mode == FailureMode.PENDING_THEN_SUCCESS:
        return ResolutionOutcome(
            apply_funds_now=True,
            ledger_status=LedgerStatus.SUCCESS,
            visible_status=VisibleStatus.SUCCESS,
            message="Transaction successful.",
        )
    if plan.mode == FailureMode.PENDING_THEN_FAILED:
        return ResolutionOutcome(
            apply_funds_now=False,
            ledger_status=LedgerStatus.FAILED,
            visible_status=VisibleStatus.FAILED,
            message="Transaction failed.",
        )
    raise AssertionError(f"resolution_outcome called for non-pending mode: {plan.mode}")
