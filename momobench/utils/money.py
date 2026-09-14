"""Exact monetary arithmetic helpers.

Money must never be represented as a binary float anywhere in MoMo Bench. All
amounts pass through :func:`money` to normalize to a two-decimal-place
``Decimal``, and are serialized as decimal strings (e.g. ``"100.00"``), never
JSON numbers.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class InvalidMoneyError(ValueError):
    """Raised when a value cannot be interpreted as a valid monetary amount."""


def money(x: str | float | Decimal) -> Decimal:
    """Normalize ``x`` to a Decimal quantized to two decimal places.

    ``float`` input is explicitly rejected (not silently coerced) because a
    float literal is already an imprecise representation of the intended
    decimal amount by the time it reaches this function.
    """
    if isinstance(x, float):
        raise InvalidMoneyError(
            f"refusing to construct money from a float ({x!r}); pass a str, "
            f"int, or Decimal instead"
        )
    try:
        d = Decimal(str(x))
    except InvalidOperation as exc:
        raise InvalidMoneyError(f"cannot parse {x!r} as a monetary amount") from exc
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def money_str(x: Decimal) -> str:
    """Serialize a Decimal money value to its canonical decimal string."""
    return str(money(x))


def require_nonnegative(amount: Decimal, *, label: str = "amount") -> Decimal:
    if amount < ZERO:
        raise InvalidMoneyError(f"{label} must be non-negative, got {amount}")
    return amount


def require_positive(amount: Decimal, *, label: str = "amount") -> Decimal:
    if amount <= ZERO:
        raise InvalidMoneyError(f"{label} must be positive, got {amount}")
    return amount
