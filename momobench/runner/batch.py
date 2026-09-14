"""Batch/experiment execution (spec §55, §57, §93): async concurrency with
per-provider semaphores, resumable episodes, and the full run-directory
layout (manifest, config snapshot, per-episode artifacts, aggregate
results).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from momobench.actions.parser import parse_action
from momobench.agents.registry import get_agent_factory, is_mock_agent, load_agents_config
from momobench.constants import (
    AGENTS_CONFIG_PATH,
    BENCHMARK_CONFIG_PATH,
    DEFAULT_FEE_POLICY_ID,
    DEFAULT_INTERFACE_PROFILE_ID,
    DEFAULT_LIMITS_POLICY_ID,
    DEFAULT_MAX_ACTION_TOKENS,
    DEFAULT_MAX_STEPS,
    RUNS_DIR,
)
from momobench.envs import make_env
from momobench.envs.tool.schema import parse_tool_action
from momobench.logging.writer import episode_dir, write_episode_artifacts
from momobench.runner.episode import run_episode
from momobench.runner.manifest import build_manifest
from momobench.runner.resume import has_valid_result, load_existing_result_row
from momobench.runner.retries import RetryingAgent
from momobench.scenarios.loader import load_scenario_dir
from momobench.scenarios.schema import Scenario
from momobench.utils.io import load_yaml


@dataclass
class ExperimentConfig:
    name: str
    scenario_dir: Path
    agents: list[str]
    interface: str = "ussd"
    repeats: int = 1
    max_steps: int = DEFAULT_MAX_STEPS
    max_action_tokens: int = DEFAULT_MAX_ACTION_TOKENS
    parallelism: dict[str, int] = field(default_factory=dict)
    require_tags: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> ExperimentConfig:
        data = load_yaml(path)
        return cls(
            name=data["name"],
            scenario_dir=Path(data["scenario_dir"]),
            agents=list(data["agents"]),
            interface=data.get("interface", "ussd"),
            repeats=int(data.get("repeats", 1)),
            max_steps=int(data.get("max_steps", DEFAULT_MAX_STEPS)),
            max_action_tokens=int(data.get("max_action_tokens", DEFAULT_MAX_ACTION_TOKENS)),
            parallelism=dict(data.get("parallelism", {})),
            require_tags=list(data.get("require_tags", [])),
        )


async def _run_one_episode(
    *,
    agent_key: str,
    scenario: Scenario,
    repeat_id: int,
    cfg: ExperimentConfig,
    run_dir: Path,
    agents_config: dict,
    semaphore: asyncio.Semaphore,
    resume: bool,
) -> dict:
    episode_id = f"{agent_key}__{scenario.scenario_id}__r{repeat_id}"

    if resume and has_valid_result(run_dir, agent_key, scenario.scenario_id, repeat_id):
        return load_existing_result_row(run_dir, agent_key, scenario.scenario_id, repeat_id)

    factory = get_agent_factory(agent_key, agents_config)

    async with semaphore:
        try:
            base_agent = factory(scenario)
            agent = base_agent if is_mock_agent(agent_key) else RetryingAgent(base_agent)
            env = make_env(cfg.interface, scenario.sender_operator, max_steps=cfg.max_steps)
            parse_fn = parse_tool_action if cfg.interface == "tool" else parse_action
            result = await run_episode(
                agent,
                env,
                scenario,
                max_steps=cfg.max_steps,
                max_action_tokens=cfg.max_action_tokens,
                parse_fn=parse_fn,
            )
        except Exception as exc:  # noqa: BLE001 - infra failures must not be scored as model failure (spec §92)
            failure_row = {
                "episode_id": episode_id,
                "scenario_id": scenario.scenario_id,
                "agent_key": agent_key,
                "repeat_id": repeat_id,
                "episode_status": "INFRA_FAILURE",
                "error": str(exc),
                "task_success": False,
                "safe_success": False,
            }
            # Persisted under a name distinct from result.json: has_valid_result()
            # only recognizes result.json, so a transient infra failure is still
            # retried on the next --resume rather than treated as done. Durable
            # storage here (rather than only the in-memory return value) is what
            # lets write_results_and_aggregate rebuild complete run-level
            # artifacts from disk after a partial (--agents subset) invocation.
            out_dir = episode_dir(run_dir, agent_key, scenario.scenario_id, repeat_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "failure.json").write_text(json.dumps(failure_row, indent=2, default=str), encoding="utf-8")
            return failure_row

    return write_episode_artifacts(
        run_dir, agent_key=agent_key, scenario=scenario, repeat_id=repeat_id,
        result=result, episode_id=episode_id,
    )


async def run_experiment(
    cfg: ExperimentConfig,
    *,
    run_dir: Path,
    resume: bool = False,
    agents_config_path: str | Path = AGENTS_CONFIG_PATH,
) -> list[dict]:
    """Episode isolation (spec §54): every episode gets a fresh env/world and
    a fresh agent instance from the factory — nothing is shared across
    episodes except the (stateless, concurrency-safe) real-provider client
    objects and the per-provider semaphore."""
    scenarios = load_scenario_dir(cfg.scenario_dir)
    if cfg.require_tags:
        required = set(cfg.require_tags)
        scenarios = [s for s in scenarios if required.issubset(set(s.tags))]
    if not scenarios:
        raise ValueError(f"no scenarios found in {cfg.scenario_dir} matching require_tags={cfg.require_tags}")

    needs_real_config = any(not is_mock_agent(a) for a in cfg.agents)
    agents_config = load_agents_config(agents_config_path) if needs_real_config else {}

    for agent_key in cfg.agents:
        if not is_mock_agent(agent_key) and agent_key not in agents_config:
            raise KeyError(f"agent {agent_key!r} is not a mock agent and is not defined in {agents_config_path}")

    semaphores: dict[str, asyncio.Semaphore] = {}

    def sem_for(agent_key: str) -> asyncio.Semaphore:
        provider = "mock" if is_mock_agent(agent_key) else agents_config[agent_key].provider
        if provider not in semaphores:
            default_limit = 8 if provider == "mock" else 4
            limit = cfg.parallelism.get(provider, cfg.parallelism.get("default", default_limit))
            semaphores[provider] = asyncio.Semaphore(max(1, int(limit)))
        return semaphores[provider]

    tasks = []
    for agent_key in cfg.agents:
        sem = sem_for(agent_key)
        for scenario in scenarios:
            for repeat_id in range(cfg.repeats):
                tasks.append(
                    _run_one_episode(
                        agent_key=agent_key,
                        scenario=scenario,
                        repeat_id=repeat_id,
                        cfg=cfg,
                        run_dir=run_dir,
                        agents_config=agents_config,
                        semaphore=sem,
                        resume=resume,
                    )
                )

    rows = await asyncio.gather(*tasks)
    return list(rows)


def load_all_episode_rows(run_dir: Path) -> list[dict]:
    """Rebuilds the complete row set for a run directory straight from the
    durable per-episode artifacts on disk, rather than trusting the
    in-memory return value of a single run_experiment() call. Necessary
    because a partial invocation (e.g. --agents one_model --resume, to
    retry just one failed/outaged model) only ever sees its own subset of
    episodes in memory — writing run-level results.csv/aggregate.json from
    that subset would silently clobber every other agent's results already
    on disk. Prefers a successful result.json over a stale failure.json for
    the same episode (a retried episode that later succeeded)."""
    episodes_root = Path(run_dir) / "episodes"
    rows: list[dict] = []
    if not episodes_root.exists():
        return rows
    for ep_dir in sorted(episodes_root.glob("*/*")):
        result_path = ep_dir / "result.json"
        failure_path = ep_dir / "failure.json"
        if result_path.exists():
            rows.append(json.loads(result_path.read_text(encoding="utf-8")))
        elif failure_path.exists():
            rows.append(json.loads(failure_path.read_text(encoding="utf-8")))
    return rows


def write_results_and_aggregate(run_dir: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(run_dir / "results.csv", index=False)
    df.to_parquet(run_dir / "results.parquet", index=False)

    failures = df[df.get("episode_status", "OK") != "OK"] if "episode_status" in df else df.iloc[0:0]
    failures.to_csv(run_dir / "failures.csv", index=False)

    scored = df[df.get("episode_status", "OK") == "OK"] if "episode_status" in df else df
    from momobench.evaluation.aggregate import aggregate_by_agent

    if len(scored):
        agg = aggregate_by_agent(scored)
        aggregate_payload = {"per_agent": agg.to_dict(orient="records")}
    else:
        aggregate_payload = {"per_agent": []}
    (run_dir / "aggregate.json").write_text(json.dumps(aggregate_payload, indent=2, default=str), encoding="utf-8")


def execute_run(
    experiment_config_path: str | Path,
    *,
    run_dir: Path | None = None,
    resume: bool = False,
    agents_config_path: str | Path = AGENTS_CONFIG_PATH,
) -> Path:
    cfg = ExperimentConfig.from_yaml(experiment_config_path)

    if run_dir is None:
        timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
        run_dir = RUNS_DIR / f"{timestamp}_{cfg.name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    snapshot_dir = run_dir / "config_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for src in (Path(agents_config_path), BENCHMARK_CONFIG_PATH, Path(experiment_config_path)):
        if src.exists():
            shutil.copy2(src, snapshot_dir / src.name)

    scenario_manifest_path = None
    candidate = cfg.scenario_dir.parent.parent / "manifests" / f"{cfg.scenario_dir.name}.json"
    if candidate.exists():
        scenario_manifest_path = candidate

    all_scenarios = load_scenario_dir(cfg.scenario_dir)
    if cfg.require_tags:
        required = set(cfg.require_tags)
        all_scenarios = [s for s in all_scenarios if required.issubset(set(s.tags))]

    manifest = build_manifest(
        experiment_name=cfg.name,
        scenario_manifest_path=scenario_manifest_path,
        agents_config_path=agents_config_path,
        experiment_config_path=experiment_config_path,
        fee_policy_id=DEFAULT_FEE_POLICY_ID,
        limits_policy_id=DEFAULT_LIMITS_POLICY_ID,
        interface_profile_id=DEFAULT_INTERFACE_PROFILE_ID,
        interface=cfg.interface,
        agent_keys=cfg.agents,
        scenario_count=len(all_scenarios),
        repeats=cfg.repeats,
    )
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    asyncio.run(
        run_experiment(cfg, run_dir=run_dir, resume=resume, agents_config_path=agents_config_path)
    )
    # Rebuilt from every durable per-episode artifact under run_dir, not just
    # this invocation's in-memory rows — see load_all_episode_rows().
    write_results_and_aggregate(run_dir, load_all_episode_rows(run_dir))

    return run_dir
