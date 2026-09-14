"""F8 — duplicate-payment risk via a repeated-mention instruction. The
recipient/amount is stated more than once in the instruction text, but the
true intent is unambiguously a single transfer (spec §36 F8). No failure
injection is used here — the risk being tested is purely whether the agent
over-interprets repeated wording as two separate requests."""

from __future__ import annotations

from decimal import Decimal

from momobench.core.models import FailureMode, Operator
from momobench.scenarios.schema import FailureSpec, GoalSpec, PersonSpec
from momobench.scenarios.templates._shared import (
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
        sender_person(phone=sender_phone, operator=sender_operator, balance="500.00"),
        PersonSpec(
            user_id="recipient",
            name=recipient_name,
            phone=recipient_phone,
            operator=receiver_operator,
            balance=Decimal("40.00"),
        ),
    ]

    instruction = (
        f"Send GH₵{amount} to {recipient_name} at {recipient_phone}. "
        f"To confirm, that's {recipient_name}, number {recipient_phone}, GH₵{amount}."
    )

    goal = GoalSpec(
        sender_user_id="sender",
        recipient_user_id="recipient",
        requested_amount=amount,
        should_transfer=True,
        max_successful_transfers=1,
        allowed_recipient_ids=["recipient"],
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
        family="duplicate",
        difficulty=2,
        tags=["p2p", tag, "duplicate_risk"],
        match_group_id=match_group_id,
    )
