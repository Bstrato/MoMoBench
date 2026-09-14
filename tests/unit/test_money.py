from decimal import Decimal

import pytest

from momobench.utils.money import InvalidMoneyError, money, require_nonnegative, require_positive


def test_decimal_addition_is_exact():
    assert money("0.10") + money("0.20") == money("0.30")


def test_quantizes_to_two_places():
    assert money("1") == Decimal("1.00")
    assert money("1.005") == Decimal("1.01")  # ROUND_HALF_UP
    assert money("1.004") == Decimal("1.00")


def test_accepts_str_int_decimal():
    assert money(100) == Decimal("100.00")
    assert money(Decimal("50.5")) == Decimal("50.50")
    assert money("50.5") == Decimal("50.50")


def test_rejects_float_input():
    with pytest.raises(InvalidMoneyError):
        money(0.1)


def test_rejects_garbage_input():
    with pytest.raises(InvalidMoneyError):
        money("not-a-number")


def test_require_nonnegative_rejects_negative():
    with pytest.raises(InvalidMoneyError):
        require_nonnegative(money("-1.00"))
    require_nonnegative(money("0.00"))


def test_require_positive_rejects_zero_and_negative():
    with pytest.raises(InvalidMoneyError):
        require_positive(money("0.00"))
    with pytest.raises(InvalidMoneyError):
        require_positive(money("-5.00"))
    require_positive(money("0.01"))
