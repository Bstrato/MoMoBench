"""Resumable execution (spec §56). A completed, valid ``result.json`` for a
given (agent, scenario, repeat) is never silently overwritten — ``--resume``
skips it; without ``--resume`` the run starts clean."""

from __future__ import annotations

import json
from pathlib import Path

from momobench.logging.writer import episode_dir

REQUIRED_RESULT_KEYS = ("episode_id", "scenario_id", "agent_key", "task_success", "safe_success")


def has_valid_result(run_dir: str | Path, agent_key: str, scenario_id: str, repeat_id: int) -> bool:
    path = episode_dir(run_dir, agent_key, scenario_id, repeat_id) / "result.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return all(key in data for key in REQUIRED_RESULT_KEYS)


def load_existing_result_row(run_dir: str | Path, agent_key: str, scenario_id: str, repeat_id: int) -> dict:
    path = episode_dir(run_dir, agent_key, scenario_id, repeat_id) / "result.json"
    return json.loads(path.read_text(encoding="utf-8"))
