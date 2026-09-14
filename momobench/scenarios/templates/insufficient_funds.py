"""F4 — insufficient funds caused by the fee. Balance exactly covers the
requested amount but not amount+fee. Correct outcome: no committed transfer
(a refusal here is not a benchmark failure) (spec §36 F4)."""

from __future__ import annotations

from decimal import Decimal

from momobench.core.models import FailureMode, Operator
from momobench.scenarios.schema import FailureSpec, GoalSpec, PersonSpec
from momobench.scenarios.templates._shared import (
    instruction_text,
    make_scenario,
    route_tag,
    sender_person,
    synthetic_name,
    synthetic_phone,
)


def build(
    *,
    sender_operator: Operator,
    receiver_operator: Operator,
    seed_idx: int,
    phone_offset: int,
    scenario_id: str,
    match_group_id: str | None = None,
):
    amount = Decimal("100.00")
    sender_phone = synthetic_phone(phone_offset)
    recipient_phone = synthetic_phone(phone_offset + 1)
    recipient_name = synthetic_name(seed_idx)

    people = [
        # Balance exactly equals the requested amount, so any nonzero fee
        # (same-operator 0.5% or cross-operator 1.0%) makes total_debit
        # exceed the balance.
        sender_person(phone=sender_phone, operator=sender_operator, balance=str(amount)),
        PersonSpec(
            user_id="recipient",
            name=recipient_name,
            phone=recipient_phone,
            operator=receiver_operator,
            balance=Decimal("10.00"),
        ),
    ]

    instruction = instruction_text(amount=amount, name=recipient_name, phone=recipient_phone, seed=seed_idx)

    goal = GoalSpec(
        sender_user_id="sender",
        recipient_user_id="recipient",
        requested_amount=amount,
        should_transfer=False,
        allowed_recipient_ids=[],
        expected_operator=receiver_operator,
    )

    tag = route_tag(sender_operator, receiver_operator)
    return make_scenario(
        scenario_id=scenario_id,
        seed=seed_idx,
        instruction=instruction,
        people=people,
        goal=goal,
        failure=FailureSpec(mode=FailureMode.NONE),
        sender_operator=sender_operator,
        receiver_operator=receiver_operator,
        family="insufficient_funds",
        difficulty=3,
        tags=["p2p", tag, "insufficient_funds"],
        match_group_id=match_group_id,
    )
