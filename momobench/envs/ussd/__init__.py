from momobench.core.models import Operator
from momobench.envs.ussd.at import ATEnv
from momobench.envs.ussd.mtn import MTNEnv
from momobench.envs.ussd.telecel import TelecelEnv

ENV_BY_OPERATOR = {
    Operator.MTN: MTNEnv,
    Operator.TELECEL: TelecelEnv,
    Operator.AT: ATEnv,
}


def make_ussd_env(operator: Operator, **kwargs):
    return ENV_BY_OPERATOR[operator](**kwargs)
