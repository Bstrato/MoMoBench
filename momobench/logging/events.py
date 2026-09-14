"""Trace event schema (spec §58)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TraceEvent:
    event_id: int
    episode_id: str
    step: int
    event_type: str
    sim_time: int | None
    wall_time_utc: str
    data: dict = field(default_factory=dict)

    def to_json_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "episode_id": self.episode_id,
            "step": self.step,
            "event_type": self.event_type,
            "sim_time": self.sim_time,
            "wall_time_utc": self.wall_time_utc,
            "data": self.data,
        }


def now_utc_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


EVENT_TYPES = (
    "episode_start",
    "observation",
    "model_request",
    "model_response",
    "action_parse_error",
    "agent_action",
    "env_transition",
    "transaction_preview",
    "ledger_event",
    "transaction_visible_result",
    "episode_terminal",
    "score",
    "episode_end",
)
