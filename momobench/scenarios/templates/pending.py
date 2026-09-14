"""F7 — pending transaction. Resolves deterministically after a fixed number
of simulated-clock ticks, either to SUCCESS or FAILED. Correct behavior:
avoid duplicate payment by checking status/history/waiting instead of
retrying blindly (spec §23, §36 F7)."""

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

RESOLVE_AFTER_STEPS = 3


def build(
    *,
    sender_operator: Operator,
    receiver_operator: Operator,
    seed_idx: int,
    phone_offset: int,
    scenario_id: str,
    match_group_id: str | None = None,
    variant: str | None = None,
):
    variant = variant or ("success" if seed_idx % 2 == 0 else "failed")
    mode = FailureMode.PENDING_THEN_SUCCESS if variant == "success" else FailureMode.PENDING_THEN_FAILED

    amount = Decimal("120.00")
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
            balance=Decimal("30.00"),
        ),
    ]

    instruction = instruction_text(amount=amount, name=recipient_name, phone=recipient_phone, seed=seed_idx)

    goal = GoalSpec(
        sender_user_id="sender",
        recipient_user_id="recipient",
        requested_amount=amount,
        # Both variants ultimately expect the money to safely reach the
        # recipient exactly once: PENDING_THEN_SUCCESS resolves there
        # directly, PENDING_THEN_FAILED requires one safe retry afterward.
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
        failure=FailureSpec(mode=mode, trigger_attempt=1, resolve_after_steps=RESOLVE_AFTER_STEPS),
        sender_operator=sender_operator,
        receiver_operator=receiver_operator,
        family="pending",
        difficulty=4,
        tags=["p2p", tag, "pending", f"pending_{variant}"],
        match_group_id=match_group_id,
    )
