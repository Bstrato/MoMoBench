"""Scenario suite validation (spec §42). Pydantic already enforces most
structural invariants at parse time (unique users/phones per scenario,
referenced user IDs exist, non-negative amounts, coherent failure specs).
This module adds the checks that require looking at policies, the whole
suite at once, or scenario semantics Pydantic can't express.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from momobench.core.errors import UnknownPolicyError
from momobench.core.fees import FeePolicy
from momobench.core.limits import LimitPolicy
from momobench.scenarios.hashing import scenario_hash
from momobench.scenarios.schema import Scenario

# Families whose should_transfer=false is expected to be backed by a
# deterministic blocking condition we can sanity-check programmatically.
BLOCKING_FAMILIES = {"recipient_mismatch", "operator_mismatch"}

_CREDENTIAL_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"sess-[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


@dataclass(frozen=True)
class ValidationIssue:
    scenario_id: str
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.scenario_id}] {self.code}: {self.message}"


def _scan_for_credentials(scenario: Scenario) -> list[ValidationIssue]:
    haystack = scenario.model_dump_json()
    issues = []
    for pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(haystack):
            issues.append(
                ValidationIssue(
                    scenario.scenario_id,
                    "possible_credential",
                    f"scenario data matches a credential-like pattern: {pattern.pattern}",
                )
            )
    return issues


def validate_scenario(scenario: Scenario, *, policies_dir: str | Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sid = scenario.scenario_id

    if scenario.goal.should_transfer and scenario.goal.requested_amount <= 0:
        issues.append(
            ValidationIssue(sid, "nonpositive_amount", "should_transfer=true but requested_amount <= 0")
        )

    if not scenario.goal.should_transfer and scenario.family not in BLOCKING_FAMILIES:
        # Not necessarily an error (insufficient_funds/limit families also
        # legitimately set should_transfer=false), but flag anything outside
        # the known deterministic-block families for manual review.
        known_amount_block_families = {"insufficient_funds", "limit_violation"}
        if scenario.family not in known_amount_block_families:
            issues.append(
                ValidationIssue(
                    sid,
                    "unclear_blocking_condition",
                    f"should_transfer=false for family {scenario.family!r}, which is not a "
                    f"recognized deterministic-block family; verify ground truth by hand",
                )
            )

    try:
        FeePolicy.from_policy_id(scenario.fee_policy_id, policies_dir)
    except UnknownPolicyError:
        issues.append(ValidationIssue(sid, "unknown_fee_policy", scenario.fee_policy_id))

    try:
        LimitPolicy.from_policy_id(scenario.limits_policy_id, policies_dir)
    except UnknownPolicyError:
        issues.append(ValidationIssue(sid, "unknown_limits_policy", scenario.limits_policy_id))

    issues.extend(_scan_for_credentials(scenario))

    return issues


def validate_suite(scenarios: list[Scenario], *, policies_dir: str | Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    ids = [s.scenario_id for s in scenarios]
    seen: set[str] = set()
    for sid in ids:
        if sid in seen:
            issues.append(ValidationIssue(sid, "duplicate_scenario_id", "scenario_id is not unique in suite"))
        seen.add(sid)

    for scenario in scenarios:
        issues.extend(validate_scenario(scenario, policies_dir=policies_dir))

    # Match-group consistency: members of the same match_group_id must hold
    # amount, starting balances, family, and failure mode constant, varying
    # only the operator route (spec §38).
    groups: dict[str, list[Scenario]] = {}
    for s in scenarios:
        if s.match_group_id:
            groups.setdefault(s.match_group_id, []).append(s)

    for group_id, members in groups.items():
        first = members[0]
        for other in members[1:]:
            if other.goal.requested_amount != first.goal.requested_amount:
                issues.append(
                    ValidationIssue(
                        other.scenario_id,
                        "match_group_amount_mismatch",
                        f"match_group {group_id!r}: requested_amount differs from {first.scenario_id}",
                    )
                )
            if other.family != first.family:
                issues.append(
                    ValidationIssue(
                        other.scenario_id,
                        "match_group_family_mismatch",
                        f"match_group {group_id!r}: family differs from {first.scenario_id}",
                    )
                )
            if other.failure.mode != first.failure.mode:
                issues.append(
                    ValidationIssue(
                        other.scenario_id,
                        "match_group_failure_mismatch",
                        f"match_group {group_id!r}: failure.mode differs from {first.scenario_id}",
                    )
                )
            if len(other.people) != len(first.people):
                issues.append(
                    ValidationIssue(
                        other.scenario_id,
                        "match_group_people_count_mismatch",
                        f"match_group {group_id!r}: people count differs from {first.scenario_id}",
                    )
                )

    return issues


def validate_hashes(scenarios: list[Scenario], manifest_hashes: dict[str, str]) -> list[ValidationIssue]:
    """Compare current scenario content hashes against a frozen manifest."""
    issues: list[ValidationIssue] = []
    for scenario in scenarios:
        expected = manifest_hashes.get(scenario.scenario_id)
        if expected is None:
            issues.append(
                ValidationIssue(scenario.scenario_id, "missing_from_manifest", "not present in frozen manifest")
            )
            continue
        actual = scenario_hash(scenario)
        if actual != expected:
            issues.append(
                ValidationIssue(
                    scenario.scenario_id,
                    "hash_mismatch",
                    f"content hash changed since freeze: expected {expected}, got {actual}",
                )
            )
    return issues
