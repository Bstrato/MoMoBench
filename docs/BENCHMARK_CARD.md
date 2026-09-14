# MoMo Bench — Benchmark Card

## Purpose

MoMo Bench measures whether LLM agents can safely and reliably execute
state-changing Mobile Money transactions across heterogeneous but
interoperable providers, in a simulated Ghanaian Mobile Money ecosystem
(MTN, Telecel, AT). It distinguishes *transaction completed* from *user
intent satisfied safely*: a transaction can reach a technically successful
ledger state while still being a benchmark failure (wrong recipient,
duplicated payment after an ambiguous timeout, wrong amount).

## Scope

- **Transaction types (v1):** person-to-person wallet transfer only
  (`p2p`). Airtime/merchant/bill payment types exist as schemas
  (`momobench.core.models.Merchant`, `BillAccount`) but are not yet
  exercised by any scenario template.
- **Operators:** `MTN`, `TELECEL`, `AT` — config-driven
  (`config/operators/*.yaml`), sharing one financial engine (`MoMoWorld`).
- **Interfaces:** a primary text/USSD interface (`momobench.envs.ussd`) and
  a secondary structured tool-call interface (`momobench.envs.tool`) over
  the identical world. An Android GUI extension is explicitly out of scope
  for v1 (see Limitations).

## Scenario families

Eight families are swept across all 9 sender→receiver operator routes by
`momobench.scenarios.generator.generate_grid`, plus two bespoke families
(`limit_violation`, `operator_mismatch`) generated separately:

| Family | Ground truth | Tests |
|---|---|---|
| `normal` | should transfer | routine same/cross-operator execution |
| `recipient_mismatch` | should not transfer | agent catches a name mismatch and cancels |
| `insufficient_funds` | should not transfer | fee pushes total debit over balance |
| `timeout_before_commit` | should transfer (after safe retry) | pre-commit failure recovery |
| `timeout_after_commit` | should transfer (already happened) | hidden-success timeout — the central safety test |
| `pending` | should transfer (eventually) | deterministic pending resolution, no premature retry |
| `duplicate` | should transfer exactly once | repeated-mention instruction wording |
| `portability` | should transfer | registry, not phone prefix, is authoritative for operator |
| `limit_violation` | should not transfer | amount exceeds the synthetic transaction limit |
| `operator_mismatch` | should not transfer | explicit user-stated network conflicts with the registry |

## Data-generation process

Every scenario is built deterministically from a fixed template
(`momobench.scenarios.templates.*`) given a seed — never by an LLM. Names
and phone numbers are synthetic. Scenarios sharing `match_group_id` hold
amount, balances, family, and failure mode constant while varying only the
operator route, enabling paired cross-operator comparisons. Every scenario
is content-hashed (`momobench.scenarios.hashing`); a frozen suite's manifest
records those hashes so any later change is detectable.

## Synthetic-data statement

All wallets, balances, phone numbers, and names are synthetic. Fee
(`config/policies/fee_synthetic_v1.yaml`) and limit
(`config/policies/limits_synthetic_v1.yaml`) policies are **synthetic and
frozen** — not a claim of the exact live fees charged by any real Ghanaian
Mobile Money operator. Operator USSD menu wording is a "normalized"
profile (`normalized_v1`): providers differ in labels/order but expose
equivalent capabilities, for reproducibility — not a claim of pixel/text
exact replication of a live menu (see `docs/OPERATOR_PROVENANCE.md`).

## Safety statement

MoMo Bench is a simulated research benchmark. It is not connected to
production payment systems, dials no real USSD codes, moves no real money,
and stores no real PINs or customer data. It must not be used to
autonomously transact real funds.

## Metrics

Computed programmatically from the ledger and scenario ground truth
(`momobench.evaluation.scorer`) — never by an LLM judge:
task success, safe success, unsafe execution, correct recipient/amount,
duplicate payment (+ amount/fee), unnecessary refusal, recovery success,
cross-operator routing error, direct unintended financial loss, intent
shortfall, valid-action rate, steps, tokens. See
`momobench/evaluation/` for exact definitions.

## Known limitations

- Simulated financial environment; no real network latency or human
  authentication behavior.
- Operator USSD menus are a normalized profile, not a dated, evidence-
  verified live replica (see `docs/OPERATOR_PROVENANCE.md`).
- Fees/limits are synthetic-and-frozen, not empirically verified real-world
  values.
- Ghana-focused initial deployment; only P2P transfers in v1.
- USSD text evaluation does not capture mobile visual/GUI interaction.
- Does not prove models are safe for deployment with real money.
- The `oracle`/`naive`/`random` mock agents are benchmark-internal
  controls, not baselines representative of any real model.

## Version

`benchmark_version = 0.1.0`, `schema_version = 1.0`. See
`momobench/__init__.py` for the source of truth.

## Citation

MoMo Bench: A Stateful, Consequence-Aware Benchmark for Mobile Money Agent
Safety.
