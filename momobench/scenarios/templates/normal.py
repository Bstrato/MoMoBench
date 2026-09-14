"""F1/F2 — normal same-operator / cross-operator transfer. Correct outcome:
exactly one successful transfer to the correct recipient for the correct
amount (spec §36 F1-F2)."""

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
        sender_person(phone=sender_phone, operator=sender_operator, balance="500.00"),
        PersonSpec(
            user_id="recipient",
            name=recipient_name,
            phone=recipient_phone,
            operator=receiver_operator,
            balance=Decimal("80.00"),
        ),
    ]

    instruction = instruction_text(amount=amount, name=recipient_name, phone=recipient_phone, seed=seed_idx)

    goal = GoalSpec(
        sender_user_id="sender",
        recipient_user_id="recipient",
        requested_amount=amount,
        should_transfer=True,
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
        family="normal",
        difficulty=1 if tag == "same_operator" else 2,
        tags=["p2p", tag, f"{sender_operator.value}_to_{receiver_operator.value}", "normal"],
        match_group_id=match_group_id,
    )
