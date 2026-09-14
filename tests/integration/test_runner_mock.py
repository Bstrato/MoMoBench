"""Full batch runner + resume behavior against the mock-agent controls
(spec §86) — no API keys required, zero cost. This is the automated version
of the manual `momobench run --experiment config/experiments/smoke.yaml`
check: proves the whole pipeline (async batch execution, per-episode
artifacts, resume, aggregation) works end-to-end."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from momobench.runner.batch import execute_run


@pytest.fixture
def smoke_experiment_path(tmp_path):
    content = """\
name: smoke_test_run
scenario_dir: data/scenarios/smoke
agents:
  - oracle
  - naive
  - random
interface: ussd
repeats: 1
max_steps: 20
max_action_tokens: 128
parallelism:
  mock: 8
"""
    path = tmp_path / "smoke_test.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_batch_run_produces_full_result_set(tmp_path, smoke_experiment_path):
    run_dir = tmp_path / "run1"
    out_dir = execute_run(smoke_experiment_path, run_dir=run_dir)

    assert out_dir == run_dir
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "results.csv").exists()
    assert (run_dir / "results.parquet").exists()
    assert (run_dir / "aggregate.json").exists()
    assert (run_dir / "failures.csv").exists()

    df = pd.read_csv(run_dir / "results.csv")
    assert len(df) == 36  # 3 agents x 12 smoke scenarios x 1 repeat
    assert set(df["agent_key"]) == {"oracle", "naive", "random"}
    assert (df["episode_status"] == "OK").all()

    aggregate = json.loads((run_dir / "aggregate.json").read_text())
    per_agent = {row["agent_key"]: row for row in aggregate["per_agent"]}
    assert per_agent["oracle"]["n_episodes"] == 12
    assert per_agent["oracle"]["safe_success_rate"] == 1.0
    assert per_agent["naive"]["safe_success_rate"] < 1.0
    assert per_agent["random"]["safe_success_rate"] < per_agent["naive"]["safe_success_rate"]

    for agent_key in ("oracle", "naive", "random"):
        agent_dir = run_dir / "episodes" / agent_key
        episode_dirs = list(agent_dir.iterdir())
        assert len(episode_dirs) == 12
        for ep_dir in episode_dirs:
            assert (ep_dir / "result.json").exists()
            assert (ep_dir / "trace.jsonl").exists()
            assert (ep_dir / "transcript.txt").exists()


def test_resume_skips_completed_episodes_and_fills_gaps(tmp_path, smoke_experiment_path):
    run_dir = tmp_path / "run2"
    execute_run(smoke_experiment_path, run_dir=run_dir)

    df_before = pd.read_csv(run_dir / "results.csv")
    assert len(df_before) == 36

    # Simulate an interrupted run: delete two episode results, then resume.
    import shutil

    deleted = [
        run_dir / "episodes" / "oracle" / "smoke_08_hidden_success_timeout_r0",
        run_dir / "episodes" / "naive" / "smoke_05_recipient_mismatch_r0",
    ]
    for d in deleted:
        assert d.exists()
        shutil.rmtree(d)

    surviving_mtimes = {}
    for p in (run_dir / "episodes").rglob("result.json"):
        surviving_mtimes[str(p)] = p.stat().st_mtime

    execute_run(smoke_experiment_path, run_dir=run_dir, resume=True)

    df_after = pd.read_csv(run_dir / "results.csv")
    assert len(df_after) == 36
    for d in deleted:
        assert (d / "result.json").exists()

    # Episodes that were never deleted must not have been recomputed/rewritten.
    for path_str, old_mtime in surviving_mtimes.items():
        assert __import__("pathlib").Path(path_str).stat().st_mtime == old_mtime


def test_no_resume_recomputes_everything(tmp_path, smoke_experiment_path):
    run_dir = tmp_path / "run3"
    execute_run(smoke_experiment_path, run_dir=run_dir)
    first_mtime = (run_dir / "results.csv").stat().st_mtime

    import time

    time.sleep(0.01)
    execute_run(smoke_experiment_path, run_dir=run_dir, resume=False)
    second_mtime = (run_dir / "results.csv").stat().st_mtime

    assert second_mtime > first_mtime
    df = pd.read_csv(run_dir / "results.csv")
    assert len(df) == 36
