"""Load/save scenario YAML files."""

from __future__ import annotations

from pathlib import Path

from momobench.scenarios.schema import Scenario
from momobench.utils.io import dump_yaml, load_yaml


def load_scenario_file(path: str | Path) -> Scenario:
    data = load_yaml(path)
    return Scenario.model_validate(data)


def load_scenario_dir(path: str | Path) -> list[Scenario]:
    scenarios = [load_scenario_file(p) for p in sorted(Path(path).glob("*.yaml"))]
    return scenarios


def save_scenario(scenario: Scenario, path: str | Path) -> None:
    dump_yaml(scenario.model_dump(mode="json"), path)


def load_scenario_by_id(scenario_id: str, search_dirs: list[str | Path]) -> Scenario:
    for d in search_dirs:
        candidate = Path(d) / f"{scenario_id}.yaml"
        if candidate.exists():
            return load_scenario_file(candidate)
    raise FileNotFoundError(
        f"scenario {scenario_id!r} not found in any of: {[str(d) for d in search_dirs]}"
    )
