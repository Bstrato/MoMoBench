"""Fee policy: config-driven, versioned, frozen at load time — never fetched
live during an episode (spec §17, §117)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from momobench.core.errors import UnknownPolicyError
from momobench.core.models import Operator
from momobench.utils.io import load_yaml
from momobench.utils.money import money


@dataclass(frozen=True)
class FeeRule:
    rate: Decimal
    minimum: Decimal
    maximum: Decimal

    def apply(self, amount: Decimal) -> Decimal:
        fee = money(amount * self.rate)
        fee = max(fee, self.minimum)
        fee = min(fee, self.maximum)
        return money(fee)


class FeePolicy:
    def __init__(self, policy_id: str, same_operator: FeeRule, cross_operator: FeeRule) -> None:
        self.policy_id = policy_id
        self.same_operator = same_operator
        self.cross_operator = cross_operator

    @classmethod
    def from_yaml(cls, path: str | Path) -> FeePolicy:
        data = load_yaml(path)
        same = data["same_operator"]
        cross = data["cross_operator"]
        return cls(
            policy_id=data["policy_id"],
            same_operator=FeeRule(
                rate=Decimal(str(same["rate"])),
                minimum=money(same["minimum"]),
                maximum=money(same["maximum"]),
            ),
            cross_operator=FeeRule(
                rate=Decimal(str(cross["rate"])),
                minimum=money(cross["minimum"]),
                maximum=money(cross["maximum"]),
            ),
        )

    @classmethod
    def from_policy_id(cls, policy_id: str, policies_dir: Path) -> FeePolicy:
        """Load a fee policy by its internal ``policy_id`` field, independent
        of the YAML filename convention (spec examples use a filename like
        ``fee_synthetic_v1.yaml`` for ``policy_id: synthetic_fee_v1``)."""
        for path in sorted(Path(policies_dir).glob("fee_*.yaml")):
            data = load_yaml(path)
            if data.get("policy_id") == policy_id:
                return cls.from_yaml(path)
        raise UnknownPolicyError(f"no fee policy found with policy_id={policy_id!r} in {policies_dir}")

    def calculate(
        self,
        sender_operator: Operator,
        receiver_operator: Operator,
        amount: Decimal,
    ) -> Decimal:
        rule = self.same_operator if sender_operator == receiver_operator else self.cross_operator
        return rule.apply(amount)
