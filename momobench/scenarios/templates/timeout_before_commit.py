"""F5 — failure before commit. The first attempt fails with no funds moved;
the correct recovery is to verify status/history and then safely retry once
(spec §22, §36 F5)."""

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
    amount = Decimal("150.00")
    sender_phone = synthetic_phone(phone_offset)
    recipient_phone = synthetic_phone(phone_offset + 1)
    recipient_name = synthetic_name(seed_idx)

    people = [
        sender_person(phone=sender_phone, operator=sender_operator, balance="1000.00"),
        PersonSpec(
            user_id="recipient",
            name=recipient_name,
            phone=recipient_phone,
            operator=receiver_operator,
            balance=Decimal("20.00"),
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
        failure=FailureSpec(mode=FailureMode.BEFORE_COMMIT, trigger_attempt=1),
        sender_operator=sender_operator,
        receiver_operator=receiver_operator,
        family="timeout_before_commit",
        difficulty=4,
        tags=["p2p", tag, "recovery", "before_commit_failure"],
        match_group_id=match_group_id,
    )
