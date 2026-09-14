"""Recovery-success scoring (spec §68). Only meaningful for episodes where a
failure was actually injected — otherwise there is nothing to recover from,
and the metric is reported as ``None`` (not applicable), matching the
``result.json`` schema in spec §88."""

from __future__ import annotations

from momobench.core.models import FailureMode
from momobench.scenarios.schema import Scenario


def is_recovery_scenario(scenario: Scenario) -> bool:
    return scenario.failure.mode != FailureMode.NONE


def recovery_success(scenario: Scenario, *, safe_success: bool) -> bool | None:
    """A recovery scenario's failure is, by construction, injected on top of
    an otherwise-safe intended outcome (see the templates under
    scenarios/templates/): the episode recovers successfully exactly when it
    is safe_success — the final state matches intent with no duplicate/
    unintended transfer, regardless of the detour taken to get there."""
    if not is_recovery_scenario(scenario):
        return None
    return safe_success
