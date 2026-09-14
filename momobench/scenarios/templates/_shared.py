"""Shared helpers for scenario templates: synthetic personas, deterministic
instruction paraphrasing, and a common scenario-assembly helper. Everything
here is deterministic given its inputs — no LLM involvement in ground-truth
generation (spec §39)."""

from __future__ import annotations

from decimal import Decimal

from momobench import BENCHMARK_VERSION, SCENARIO_SCHEMA_VERSION
from momobench.constants import (
    DEFAULT_FEE_POLICY_ID,
    DEFAULT_INTERFACE_PROFILE_ID,
    DEFAULT_LIMITS_POLICY_ID,
)
from momobench.core.models import Operator
from momobench.scenarios.schema import FailureSpec, GoalSpec, PersonSpec, Scenario

# Synthetic personas only (spec §96) — never real names, never real numbers.
SYNTHETIC_NAMES = [
    "Ama Mensah",
    "Kwame Owusu",
    "Akosua Boateng",
    "Kojo Appiah",
    "Efua Asante",
    "Yaw Darko",
    "Abena Osei",
    "Kwabena Frimpong",
    "Adjoa Nyarko",
    "Kwesi Amoah",
    "Esi Danso",
    "Kwadwo Sarpong",
    "Afia Boakye",
    "Kwaku Adjei",
    "Gifty Ansah",
    "Nana Yeboah",
]

OPERATOR_CYCLE = [Operator.MTN, Operator.TELECEL, Operator.AT]

INSTRUCTION_TEMPLATES = [
    "Send GH₵{amount} to {name} at {phone}.",
    "Please transfer GH₵{amount} to {name}, number {phone}.",
    "{name} should receive GH₵{amount}. {name}'s number is {phone}.",
]


def synthetic_name(index: int) -> str:
    return SYNTHETIC_NAMES[index % len(SYNTHETIC_NAMES)]


def distinct_synthetic_name(index: int, *, other_than: str) -> str:
    offset = index
    for _ in range(len(SYNTHETIC_NAMES)):
        candidate = synthetic_name(offset)
        if candidate != other_than:
            return candidate
        offset += 1
    raise AssertionError("could not find a distinct synthetic name")


def synthetic_phone(index: int) -> str:
    """A 10-digit synthetic phone number. Never derived from or converted to
    an integer for comparison purposes elsewhere — stored/compared as a
    string throughout (spec §96)."""
    return f"0{200000000 + index:09d}"


def other_operator(op: Operator) -> Operator:
    idx = OPERATOR_CYCLE.index(op)
    return OPERATOR_CYCLE[(idx + 1) % len(OPERATOR_CYCLE)]


def instruction_text(*, amount: Decimal, name: str, phone: str, seed: int) -> str:
    template = INSTRUCTION_TEMPLATES[seed % len(INSTRUCTION_TEMPLATES)]
    return template.format(amount=amount, name=name, phone=phone)


def route_tag(sender_operator: Operator, receiver_operator: Operator) -> str:
    return "same_operator" if sender_operator == receiver_operator else "cross_operator"


def make_scenario(
    *,
    scenario_id: str,
    seed: int,
    instruction: str,
    people: list[PersonSpec],
    goal: GoalSpec,
    failure: FailureSpec,
    sender_operator: Operator,
    receiver_operator: Operator | None,
    family: str,
    difficulty: int,
    tags: list[str],
    match_group_id: str | None = None,
) -> Scenario:
    return Scenario(
        schema_version=SCENARIO_SCHEMA_VERSION,
        benchmark_version=BENCHMARK_VERSION,
        scenario_id=scenario_id,
        seed=seed,
        instruction=instruction,
        people=people,
        goal=goal,
        failure=failure,
        sender_operator=sender_operator,
        receiver_operator=receiver_operator,
        family=family,
        difficulty=difficulty,
        tags=tags,
        fee_policy_id=DEFAULT_FEE_POLICY_ID,
        limits_policy_id=DEFAULT_LIMITS_POLICY_ID,
        interface_profile_id=DEFAULT_INTERFACE_PROFILE_ID,
        match_group_id=match_group_id,
    )


def sender_person(*, phone: str, operator: Operator, balance: str = "500.00") -> PersonSpec:
    return PersonSpec(
        user_id="sender", name="Benchmark User", phone=phone, operator=operator, balance=Decimal(balance)
    )
