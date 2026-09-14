from __future__ import annotations

from momobench.constants import OPERATORS_DIR
from momobench.core.models import Operator
from momobench.envs.ussd.base import BaseUSSDEnv


class ATEnv(BaseUSSDEnv):
    def __init__(self, **kwargs) -> None:
        self.operator = Operator.AT
        self.config_path = OPERATORS_DIR / "at.yaml"
        super().__init__(**kwargs)
