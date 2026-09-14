from __future__ import annotations

from momobench.constants import OPERATORS_DIR
from momobench.core.models import Operator
from momobench.envs.ussd.base import BaseUSSDEnv


class MTNEnv(BaseUSSDEnv):
    def __init__(self, **kwargs) -> None:
        self.operator = Operator.MTN
        self.config_path = OPERATORS_DIR / "mtn.yaml"
        super().__init__(**kwargs)
