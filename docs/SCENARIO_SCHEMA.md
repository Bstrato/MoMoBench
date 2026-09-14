# Scenario Schema

Source of truth: `momobench/scenarios/schema.py` (Pydantic). This document
is a human-readable companion, not a second copy of the validation logic —
if the two disagree, the code wins.

## `PersonSpec`

| Field | Type | Notes |
|---|---|---|
| `user_id` | str | unique within the scenario |
| `name` | str | synthetic only |
| `phone` | str | 10-digit synthetic number; stored/compared as a string, never an int |
| `operator` | `Operator` | the person's **current** operator (registry truth) |
| `original_operator` | `Operator \| None` | pre-port operator, if `ported=True` |
| `ported` | bool | default `False` |
| `balance` | Decimal | must be non-negative |

## `GoalSpec`

| Field | Type | Notes |
|---|---|---|
| `transaction_type` | `TxType` | `p2p` in v1 |
| `sender_user_id` | str | must match a `PersonSpec.user_id` |
| `recipient_user_id` | str \| None | the *correct* recipient, or `None` if none should be paid |
| `requested_amount` | Decimal | must be non-negative |
| `should_transfer` | bool | the ground-truth safety verdict |
| `max_successful_transfers` | int | default 1; used for duplicate-payment detection |
| `allowed_recipient_ids` | list[str] | wallets a successful transfer is permitted to reach |
| `expected_operator` | `Operator \| None` | the registry-authoritative destination operator |

## `FailureSpec`

| Field | Type | Notes |
|---|---|---|
| `mode` | `FailureMode` | `none`, `before_commit`, `timeout_after_commit`, `pending_then_success`, `pending_then_failed`, `network_unavailable` |
| `trigger_attempt` | int | which commit attempt (1-indexed) the mode applies to; every other attempt is a normal success |
| `resolve_after_steps` | int \| None | pending modes only — simulated-clock ticks until resolution |

## `Scenario`

Top-level fields not already covered above: `schema_version`,
`benchmark_version`, `scenario_id` (unique), `seed`, `instruction` (the only
text the agent ever sees of the scenario), `people: list[PersonSpec]`,
`goal: GoalSpec`, `failure: FailureSpec`, `sender_operator`,
`receiver_operator`, `family`, `difficulty` (1-4, metadata only — never used
in scoring), `tags`, `fee_policy_id`, `limits_policy_id`,
`interface_profile_id`, `match_group_id` (links scenarios that vary only
the operator route, spec §38).

## Validation

`momobench.scenarios.validator.validate_suite` checks, beyond what Pydantic
enforces at parse time: duplicate scenario IDs across a suite, fee/limits
policy existence, a heuristic scan for credential-like strings, and
match-group consistency (amount/family/failure-mode/people-count held
constant across a group). `momobench.scenarios.hashing.scenario_hash`
content-hashes each scenario for freeze/drift detection.
