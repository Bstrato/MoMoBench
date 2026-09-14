"""Environment factory: dispatches on interface mode (spec §100-101). USSD
is the primary text interface; the structured tool interface is added
alongside it, sharing the identical ``MoMoWorld``."""

from __future__ import annotations

from momobench.constants import DEFAULT_MAX_STEPS
from momobench.core.models import Operator
from momobench.envs.base import BaseMoMoEnv

INTERFACE_MODES = ("ussd", "tool")


def make_env(interface: str, operator: Operator, *, max_steps: int = DEFAULT_MAX_STEPS) -> BaseMoMoEnv:
    if interface == "ussd":
        from momobench.envs.ussd import make_ussd_env

        return make_ussd_env(operator, max_steps=max_steps)
    if interface == "tool":
        from momobench.envs.tool.env import ToolEnv

        return ToolEnv(max_steps=max_steps)
    raise ValueError(f"unknown interface mode: {interface!r}; expected one of {INTERFACE_MODES}")
