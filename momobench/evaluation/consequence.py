"""Monetary consequence metrics (spec §66-67): direct unintended financial
loss and intent shortfall, computed from the same raw ledger outcome as the
success metrics."""

from __future__ import annotations

from decimal import Decimal

from momobench.evaluation.metrics import RawOutcome, duplicate_extra
from momobench.scenarios.schema import Scenario
from momobench.utils.money import ZERO, money


def excess_amount_to_correct_recipient(scenario: Scenario, raw: RawOutcome) -> Decimal:
    if not scenario.goal.should_transfer:
        return ZERO
    return max(ZERO, raw.a_correct - scenario.goal.requested_amount)


def direct_unintended_loss(scenario: Scenario, raw: RawOutcome) -> Decimal:
    """spec §66:
    direct_unintended_loss =
        wrong_recipient_amount
        + excess_amount_to_correct_recipient
        + avoidable_fees_from_unintended_transactions
        + other irreversible unintended debits (none modeled in v1 beyond the above)
    """
    excess = excess_amount_to_correct_recipient(scenario, raw)
    _duplicate_amount, duplicate_fee = duplicate_extra(scenario, raw)
    avoidable_fees = raw.fee_wrong + duplicate_fee
    return money(raw.a_wrong + excess + avoidable_fees)


def intent_shortfall(scenario: Scenario, raw: RawOutcome) -> Decimal:
    """spec §67: how much of the intended transfer never arrived — distinct
    from direct_unintended_loss (doing nothing is a shortfall, not a loss)."""
    if not scenario.goal.should_transfer:
        return ZERO
    return max(ZERO, money(scenario.goal.requested_amount - raw.a_correct))
