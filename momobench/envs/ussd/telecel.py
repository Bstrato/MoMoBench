from __future__ import annotations

from momobench.constants import OPERATORS_DIR
from momobench.core.models import Operator
from momobench.envs.ussd.base import BaseUSSDEnv


class TelecelEnv(BaseUSSDEnv):
    def __init__(self, **kwargs) -> None:
        self.operator = Operator.TELECEL
        self.config_path = OPERATORS_DIR / "telecel.yaml"
        super().__init__(**kwargs)
