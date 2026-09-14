"""Pydantic scenario schema (spec §34-38).

A scenario carries the full hidden ground truth for one episode: the people
and their starting balances/operators, the sender's goal (what a *safe*
agent should accomplish), the failure-injection plan, and bookkeeping
(policy IDs, interface profile, match-group membership for cross-operator
paired analysis). None of this is shown directly to the agent — the
environment layer renders only what a real interface would reveal.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from momobench.core.models import FailureMode, Operator, TxType


class PersonSpec(BaseModel):
    user_id: str
    name: str
    phone: str
    operator: Operator
    original_operator: Operator | None = None
    ported: bool = False
    balance: Decimal

    @field_validator("balance")
    @classmethod
    def _balance_nonnegative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("balance must be non-negative")
        return v


class GoalSpec(BaseModel):
    transaction_type: TxType = TxType.P2P
    sender_user_id: str
    recipient_user_id: str | None = None
    requested_amount: Decimal

    should_transfer: bool

    max_successful_transfers: int = 1
    allowed_recipient_ids: list[str] = Field(default_factory=list)
    expected_operator: Operator | None = None

    @field_validator("requested_amount")
    @classmethod
    def _amount_nonnegative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("requested_amount must be non-negative")
        return v


class FailureSpec(BaseModel):
    mode: FailureMode = FailureMode.NONE
    trigger_attempt: int = 1
    resolve_after_steps: int | None = None

    @model_validator(mode="after")
    def _coherent(self) -> FailureSpec:
        pending_modes = (FailureMode.PENDING_THEN_SUCCESS, FailureMode.PENDING_THEN_FAILED)
        if self.mode in pending_modes and self.resolve_after_steps is not None and self.resolve_after_steps < 1:
            raise ValueError("resolve_after_steps must be >= 1 for pending failure modes")
        if self.mode not in pending_modes and self.resolve_after_steps is not None:
            raise ValueError("resolve_after_steps only applies to pending failure modes")
        if self.trigger_attempt < 1:
            raise ValueError("trigger_attempt must be >= 1")
        return self


class Scenario(BaseModel):
    schema_version: str
    benchmark_version: str

    scenario_id: str
    seed: int

    instruction: str

    people: list[PersonSpec]
    goal: GoalSpec
    failure: FailureSpec = Field(default_factory=FailureSpec)

    sender_operator: Operator
    receiver_operator: Operator | None = None

    family: str
    difficulty: int = 1
    tags: list[str] = Field(default_factory=list)

    fee_policy_id: str
    limits_policy_id: str
    interface_profile_id: str

    match_group_id: str | None = None

    @model_validator(mode="after")
    def _referenced_users_exist(self) -> Scenario:
        known_ids = {p.user_id for p in self.people}
        if self.goal.sender_user_id not in known_ids:
            raise ValueError(f"goal.sender_user_id {self.goal.sender_user_id!r} not in people")
        if self.goal.recipient_user_id is not None and self.goal.recipient_user_id not in known_ids:
            raise ValueError(f"goal.recipient_user_id {self.goal.recipient_user_id!r} not in people")
        for rid in self.goal.allowed_recipient_ids:
            if rid not in known_ids:
                raise ValueError(f"goal.allowed_recipient_ids contains unknown user_id {rid!r}")
        return self

    @model_validator(mode="after")
    def _unique_users_and_phones(self) -> Scenario:
        user_ids = [p.user_id for p in self.people]
        if len(user_ids) != len(set(user_ids)):
            raise ValueError("duplicate user_id in people")
        phones = [p.phone for p in self.people]
        if len(phones) != len(set(phones)):
            raise ValueError("duplicate phone in people")
        return self
