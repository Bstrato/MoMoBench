from decimal import Decimal

import pytest

from momobench.constants import POLICIES_DIR
from momobench.core.errors import UnknownPolicyError
from momobench.core.fees import FeePolicy
from momobench.core.models import Operator


@pytest.fixture
def fee_policy() -> FeePolicy:
    return FeePolicy.from_policy_id("synthetic_fee_v1", POLICIES_DIR)


def test_loads_by_policy_id_not_filename(fee_policy):
    assert fee_policy.policy_id == "synthetic_fee_v1"


def test_unknown_policy_id_raises():
    with pytest.raises(UnknownPolicyError):
        FeePolicy.from_policy_id("does_not_exist", POLICIES_DIR)


def test_same_operator_fee_rate(fee_policy):
    fee = fee_policy.calculate(Operator.MTN, Operator.MTN, Decimal("100.00"))
    assert fee == Decimal("0.50")  # 0.5% of 100


def test_cross_operator_fee_rate(fee_policy):
    fee = fee_policy.calculate(Operator.MTN, Operator.TELECEL, Decimal("100.00"))
    assert fee == Decimal("1.00")  # 1.0% of 100


def test_fee_minimum_floor(fee_policy):
    fee = fee_policy.calculate(Operator.MTN, Operator.MTN, Decimal("1.00"))
    assert fee >= fee_policy.same_operator.minimum


def test_fee_maximum_cap(fee_policy):
    fee = fee_policy.calculate(Operator.MTN, Operator.TELECEL, Decimal("5000.00"))
    assert fee == fee_policy.cross_operator.maximum


def test_fee_rounding_half_up():
    # 0.5% of 33.33 = 0.16665 -> rounds to 0.17
    policy = FeePolicy.from_policy_id("synthetic_fee_v1", POLICIES_DIR)
    fee = policy.calculate(Operator.MTN, Operator.MTN, Decimal("33.33"))
    assert fee == Decimal("0.17")
