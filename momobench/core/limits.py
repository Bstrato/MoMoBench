"""Transaction limit policy: config-driven, versioned (spec §18). Limits are
never hard-coded in operator UI code — the UI layer only renders the
blocking reason the world/limit policy produces."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from momobench.core.errors import UnknownPolicyError
from momobench.utils.io import load_yaml
from momobench.utils.money import money


@dataclass(frozen=True)
class LimitViolation:
    code: str
    message: str


class LimitPolicy:
    def __init__(
        self,
        policy_id: str,
        per_tx_minimum: Decimal,
        per_tx_maximum: Decimal,
        daily_outgoing_maximum: Decimal,
    ) -> None:
        self.policy_id = policy_id
        self.per_tx_minimum = per_tx_minimum
        self.per_tx_maximum = per_tx_maximum
        self.daily_outgoing_maximum = daily_outgoing_maximum

    @classmethod
    def from_yaml(cls, path: str | Path) -> LimitPolicy:
        data = load_yaml(path)
        return cls(
            policy_id=data["policy_id"],
            per_tx_minimum=money(data["per_transaction"]["minimum"]),
            per_tx_maximum=money(data["per_transaction"]["maximum"]),
            daily_outgoing_maximum=money(data["daily_outgoing"]["maximum"]),
        )

    @classmethod
    def from_policy_id(cls, policy_id: str, policies_dir: Path) -> LimitPolicy:
        for path in sorted(Path(policies_dir).glob("limits_*.yaml")):
            data = load_yaml(path)
            if data.get("policy_id") == policy_id:
                return cls.from_yaml(path)
        raise UnknownPolicyError(f"no limits policy found with policy_id={policy_id!r} in {policies_dir}")

    def check(self, amount: Decimal, *, prior_outgoing_today: Decimal) -> LimitViolation | None:
        if amount < self.per_tx_minimum:
            return LimitViolation(
                code="below_minimum",
                message=f"Amount is below the minimum transaction amount of {self.per_tx_minimum}.",
            )
        if amount > self.per_tx_maximum:
            return LimitViolation(
                code="above_maximum",
                message=f"Amount exceeds the maximum transaction amount of {self.per_tx_maximum}.",
            )
        if prior_outgoing_today + amount > self.daily_outgoing_maximum:
            return LimitViolation(
                code="daily_limit_exceeded",
                message=f"This transaction would exceed the daily outgoing limit of "
                f"{self.daily_outgoing_maximum}.",
            )
        return None
