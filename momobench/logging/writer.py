"""JSONL trace writer, plus the episode-artifact writer used by the batch
runner (spec §57-58): ``trace.jsonl``, ``result.json``, ``transcript.txt``
per episode directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Self

from momobench.logging.events import TraceEvent, now_utc_iso
from momobench.logging.redact import redact_value
from momobench.runner.episode import EpisodeResult
from momobench.scenarios.schema import Scenario


class TraceWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8")
        self._next_id = 1

    def write(self, *, episode_id: str, step: int, event_type: str, sim_time: int | None, data: dict) -> None:
        event = TraceEvent(
            event_id=self._next_id,
            episode_id=episode_id,
            step=step,
            event_type=event_type,
            sim_time=sim_time,
            wall_time_utc=now_utc_iso(),
            data=redact_value(data),
        )
        self._next_id += 1
        self._file.write(json.dumps(event.to_json_dict(), default=str) + "\n")

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def episode_dir(run_dir: str | Path, agent_key: str, scenario_id: str, repeat_id: int) -> Path:
    return Path(run_dir) / "episodes" / agent_key / f"{scenario_id}_r{repeat_id}"


def build_result_row(
    *, episode_id: str, agent_key: str, scenario: Scenario, repeat_id: int, result: EpisodeResult
) -> dict:
    """The canonical, complete per-episode result shape — written to
    ``result.json`` and used directly as a ``results.csv`` row. Built in
    exactly one place so a resumed episode (reloaded from ``result.json``)
    and a freshly-computed one are never missing fields relative to each
    other (spec §56 resume correctness)."""
    return {
        "episode_id": episode_id,
        "scenario_id": scenario.scenario_id,
        "agent_key": agent_key,
        "provider": result.provider,
        "model": result.model,
        "repeat_id": repeat_id,
        **result.score.to_json_dict(),
        "steps": result.total_turns,
        "format_errors": result.format_errors,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms_total": result.latency_ms_total,
        "terminated": result.terminated,
        "truncated": result.truncated,
        "family": scenario.family,
        "difficulty": scenario.difficulty,
        "sender_operator": scenario.sender_operator.value,
        "receiver_operator": scenario.receiver_operator.value if scenario.receiver_operator else None,
        "failure_mode": scenario.failure.mode.value,
        "ported": any(p.ported for p in scenario.people),
        "match_group_id": scenario.match_group_id,
        "episode_status": "OK",
    }


def write_episode_artifacts(
    run_dir: str | Path,
    *,
    agent_key: str,
    scenario: Scenario,
    repeat_id: int,
    result: EpisodeResult,
    episode_id: str,
) -> dict:
    scenario_id = scenario.scenario_id
    out_dir = episode_dir(run_dir, agent_key, scenario_id, repeat_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    with TraceWriter(out_dir / "trace.jsonl") as writer:
        writer.write(episode_id=episode_id, step=0, event_type="episode_start", sim_time=0, data={"scenario_id": scenario_id})
        for i, event in enumerate(result.trace, start=1):
            writer.write(
                episode_id=episode_id,
                step=i,
                event_type=event.get("event_type", "unknown"),
                sim_time=None,
                data=event,
            )
        writer.write(
            episode_id=episode_id,
            step=len(result.trace) + 1,
            event_type="score",
            sim_time=None,
            data=result.score.to_json_dict(),
        )
        writer.write(
            episode_id=episode_id,
            step=len(result.trace) + 2,
            event_type="episode_end",
            sim_time=None,
            data={"terminated": result.terminated, "truncated": result.truncated},
        )

    result_payload = build_result_row(
        episode_id=episode_id, agent_key=agent_key, scenario=scenario, repeat_id=repeat_id, result=result
    )
    (out_dir / "result.json").write_text(
        json.dumps(redact_value(result_payload), indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    transcript_lines = []
    for msg in result.transcript:
        transcript_lines.append(f"--- {msg['role']} ---")
        transcript_lines.append(redact_value(msg["content"]))
        transcript_lines.append("")
    (out_dir / "transcript.txt").write_text(redact_value("\n".join(transcript_lines)), encoding="utf-8")

    return result_payload
