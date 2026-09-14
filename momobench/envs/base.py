"""A Gym-like base environment interface, without a Gymnasium dependency
(spec §30). ``terminated`` means a natural terminal state (the agent called
finish, or the episode reached a definitive outcome); ``truncated`` means
the step budget was exhausted."""

from __future__ import annotations

from dataclasses import dataclass, field

from momobench.actions.schema import AgentAction


@dataclass
class StepResult:
    observation: str
    terminated: bool
    truncated: bool
    info: dict = field(default_factory=dict)


class BaseMoMoEnv:
    def reset(self, scenario) -> str:
        raise NotImplementedError

    def step(self, action: AgentAction) -> StepResult:
        raise NotImplementedError

    def render(self) -> str:
        raise NotImplementedError
