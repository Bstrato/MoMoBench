"""Run manifest (spec §59) — everything needed to reproduce a result set:
versions, hashes, environment, and policy IDs. Archived alongside every run
(spec §120)."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.metadata as importlib_metadata
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from momobench import BENCHMARK_VERSION
from momobench.agents.prompts import system_prompt_hash
from momobench.constants import REPO_ROOT

TRACKED_PACKAGES = (
    "pydantic",
    "pyyaml",
    "typer",
    "rich",
    "httpx",
    "tenacity",
    "openai",
    "anthropic",
    "together",
    "python-dotenv",
    "pandas",
    "pyarrow",
)


def _file_hash(path: str | Path) -> str:
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _git_commit_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:  # noqa: BLE001 - git not being available is fine, this is best-effort
        return None


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for pkg in TRACKED_PACKAGES:
        try:
            versions[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            versions[pkg] = None
    return versions


def build_manifest(
    *,
    experiment_name: str,
    scenario_manifest_path: str | Path | None,
    agents_config_path: str | Path,
    experiment_config_path: str | Path,
    fee_policy_id: str,
    limits_policy_id: str,
    interface_profile_id: str,
    interface: str,
    agent_keys: list[str],
    scenario_count: int,
    repeats: int,
) -> dict[str, Any]:
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "git_commit": _git_commit_sha(),
        "scenario_manifest_hash": _file_hash(scenario_manifest_path) if scenario_manifest_path else None,
        "agent_config_hash": _file_hash(agents_config_path),
        "experiment_config_hash": _file_hash(experiment_config_path),
        "python_version": sys.version,
        "package_versions": _package_versions(),
        "date_utc": dt.datetime.now(dt.UTC).isoformat(),
        "machine": platform.platform(),
        "fee_policy_id": fee_policy_id,
        "limits_policy_id": limits_policy_id,
        "interface_profile_id": interface_profile_id,
        "interface": interface,
        "system_prompt_hash": system_prompt_hash(),
        "num_agents": len(agent_keys),
        "agent_keys": list(agent_keys),
        "num_scenarios": scenario_count,
        "repeats": repeats,
        "experiment_name": experiment_name,
    }
