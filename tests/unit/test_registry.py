import pytest

from momobench.core.errors import UnknownNumberError
from momobench.core.models import Operator
from momobench.core.registry import NumberRegistry


def test_register_and_resolve():
    reg = NumberRegistry()
    reg.register_number(
        phone="0200000002", user_id="ama", wallet_id="w_ama", operator=Operator.TELECEL
    )
    record = reg.resolve_number("0200000002")
    assert record.current_operator == Operator.TELECEL
    assert record.original_operator == Operator.TELECEL
    assert record.ported is False


def test_unknown_number_raises():
    reg = NumberRegistry()
    with pytest.raises(UnknownNumberError):
        reg.resolve_number("0000000000")


def test_try_resolve_returns_none_for_unknown():
    reg = NumberRegistry()
    assert reg.try_resolve_number("0000000000") is None


def test_ported_number_retains_same_number_but_changes_operator():
    reg = NumberRegistry()
    reg.register_number(
        phone="0240000009",
        user_id="kofi",
        wallet_id="w_kofi",
        operator=Operator.MTN,
    )
    before = reg.resolve_number("0240000009")
    assert before.ported is False

    after = reg.port_number("0240000009", Operator.TELECEL)

    assert after.phone == "0240000009"  # phone string unchanged
    assert after.wallet_id == before.wallet_id  # same wallet (v1: one wallet per person)
    assert after.current_operator == Operator.TELECEL
    assert after.original_operator == Operator.MTN  # history preserved
    assert after.ported is True


def test_prefix_is_not_authoritative():
    """A number can carry an MTN-looking prefix while the registry says the
    number currently resolves to Telecel — the registry, not the prefix,
    is the source of truth."""
    reg = NumberRegistry()
    reg.register_number(
        phone="0240000009",  # looks like an MTN prefix
        user_id="kofi",
        wallet_id="w_kofi",
        operator=Operator.MTN,
        original_operator=Operator.MTN,
    )
    reg.port_number("0240000009", Operator.TELECEL)
    resolved = reg.resolve_number("0240000009")
    assert resolved.current_operator == Operator.TELECEL
