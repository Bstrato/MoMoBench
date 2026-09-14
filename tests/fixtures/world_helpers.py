"""Minimal scenario-shaped test fixtures for exercising MoMoWorld directly,
without depending on the full Pydantic Scenario schema (momobench.scenarios).
Field names intentionally match momobench.scenarios.schema.{PersonSpec,
FailureSpec} exactly, so MoMoWorld.reset() works identically against either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from momobench.core.models import FailureMode, Operator


@dataclass
class FakePersonSpec:
    user_id: str
    name: str
    phone: str
    operator: Operator
    balance: Decimal
    original_operator: Operator | None = None
    ported: bool = False


@dataclass
class FakeFailureSpec:
    mode: FailureMode = FailureMode.NONE
    trigger_attempt: int = 1
    resolve_after_steps: int | None = None


@dataclass
class FakeScenario:
    scenario_id: str
    people: list[FakePersonSpec]
    failure: FakeFailureSpec = field(default_factory=FakeFailureSpec)
    fee_policy_id: str = "synthetic_fee_v1"
    limits_policy_id: str = "synthetic_limits_v1"


def two_party_scenario(
    *,
    scenario_id: str = "test_scenario",
    sender_operator: Operator = Operator.MTN,
    receiver_operator: Operator = Operator.TELECEL,
    sender_balance: str = "500.00",
    receiver_balance: str = "80.00",
    failure: FakeFailureSpec | None = None,
    sender_phone: str = "0550000001",
    receiver_phone: str = "0200000002",
    receiver_name: str = "Ama Mensah",
) -> FakeScenario:
    return FakeScenario(
        scenario_id=scenario_id,
        people=[
            FakePersonSpec(
                user_id="sender",
                name="Benchmark User",
                phone=sender_phone,
                operator=sender_operator,
                balance=Decimal(sender_balance),
            ),
            FakePersonSpec(
                user_id="ama",
                name=receiver_name,
                phone=receiver_phone,
                operator=receiver_operator,
                balance=Decimal(receiver_balance),
            ),
        ],
        failure=failure or FakeFailureSpec(),
    )
