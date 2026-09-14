"""Mobile number registry / portability.

A phone-number prefix must never be treated as authoritative operator
identity. The registry is the only source of truth for "which operator does
this number currently resolve to" — supporting scenarios where a number was
ported to a different operator than its prefix would suggest, or where a
user's *claimed* operator disagrees with the registry's current resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from momobench.core.errors import UnknownNumberError
from momobench.core.models import Operator


@dataclass(frozen=True)
class NumberRecord:
    phone: str
    user_id: str
    wallet_id: str
    current_operator: Operator
    original_operator: Operator | None = None
    ported: bool = False


class NumberRegistry:
    def __init__(self) -> None:
        self._by_phone: dict[str, NumberRecord] = {}

    def register_number(
        self,
        *,
        phone: str,
        user_id: str,
        wallet_id: str,
        operator: Operator,
        original_operator: Operator | None = None,
        ported: bool = False,
    ) -> NumberRecord:
        record = NumberRecord(
            phone=phone,
            user_id=user_id,
            wallet_id=wallet_id,
            current_operator=operator,
            original_operator=original_operator if original_operator is not None else operator,
            ported=ported,
        )
        self._by_phone[phone] = record
        return record

    def resolve_number(self, phone: str) -> NumberRecord:
        record = self._by_phone.get(phone)
        if record is None:
            raise UnknownNumberError(f"no registered number: {phone!r}")
        return record

    def try_resolve_number(self, phone: str) -> NumberRecord | None:
        return self._by_phone.get(phone)

    def port_number(self, phone: str, new_operator: Operator) -> NumberRecord:
        """Port ``phone`` to ``new_operator``. The phone string does not
        change and the wallet_id does not change (v1 is one wallet per
        person); only ``current_operator`` and ``ported`` are updated. No
        automatic prefix reclassification occurs elsewhere in the system.
        """
        existing = self.resolve_number(phone)
        updated = replace(existing, current_operator=new_operator, ported=True)
        self._by_phone[phone] = updated
        return updated

    def all_records(self) -> tuple[NumberRecord, ...]:
        return tuple(self._by_phone.values())
