"""Canonical JSON + SHA-256 content hashing for scenarios (spec §41). Once a
suite is frozen for final experiments, any change to a scenario file
requires a new benchmark version — this hash is what makes that detectable.
"""

from __future__ import annotations

import hashlib
import json

from momobench.scenarios.schema import Scenario


def canonical_json(scenario: Scenario) -> str:
    data = scenario.model_dump(mode="json")
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def scenario_hash(scenario: Scenario) -> str:
    digest = hashlib.sha256(canonical_json(scenario).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def suite_manifest(scenarios: list[Scenario], *, suite: str, benchmark_version: str) -> dict:
    return {
        "benchmark_version": benchmark_version,
        "suite": suite,
        "scenario_count": len(scenarios),
        "scenario_hashes": {s.scenario_id: scenario_hash(s) for s in scenarios},
    }
