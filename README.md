# MoMo Bench

A stateful, consequence-aware benchmark for evaluating whether LLM agents can safely
and reliably execute Mobile Money transactions across heterogeneous but interoperable
providers, in a simulated Ghanaian Mobile Money ecosystem (MTN, Telecel, AT).

## Why

Mobile Money is the dominant way hundreds of millions of people in Sub-Saharan Africa
move money, largely through USSD menus. A transaction can reach a technically
"successful" ledger state while still being unsafe: money sent to the wrong recipient,
a payment silently duplicated after an ambiguous timeout, an amount that doesn't match
what the user asked for. MoMo Bench distinguishes *transaction completed* from *user
intent satisfied safely*, and scores every episode programmatically off an
authoritative, deterministic financial ledger — never with an LLM judge.

## How it works

A single shared financial engine, `MoMoWorld` (wallets, ledger, fees, limits, a
simulated clock, deterministic failure injection, a mobile-number-portability
registry), sits behind three provider-specific USSD interaction layers (MTN, Telecel,
AT) that differ only in menu wording, never in financial semantics, plus a structured
tool-call interface as an alternative to raw USSD text. LLM agents interact through a
common JSON action protocol via adapters for OpenAI, Anthropic, Together AI, and
self-hosted vLLM models. Every scenario is generated deterministically from a fixed
template and seed — never by an LLM — and scored by a programmatic evaluator against
ledger state and scenario ground truth.

## Contributions
## A stateful, multi-operator benchmark for executable Mobile Money agents.
We introduce MoMoBench and its deterministic transaction engine for evaluating LLM agents on state-changing Mobile Money tasks across three interoperable synthetic operator environments. The benchmark represents balances, recipients, operator routing, fees, transaction limits, transaction histories, and intermediate transaction states, and supports both same-operator and cross-operator transfers. Unlike financial benchmarks centered on question answering, research, or tool selection, MoMoBench evaluates the consequences of actions that modify an authoritative financial ledger.
## A consequence-aware evaluation protocol for transactional safety.
We introduce ten controlled scenario families that test normal execution, identity and operator verification, insufficient funds, transaction limits, duplicate-payment risk, pending states, portability, and failures occurring on either side of ledger commit. Episodes are scored directly from environment state using metrics for task outcome, unsafe execution, wrong-recipient and wrong-amount transfers, duplicate payments, recovery, unnecessary refusal, simulated financial loss, intent shortfall, action validity, steps, and token usage. This separates successful execution from the correctness, safety, and material consequences of the execution process.
## A controlled study of interface sensitivity, interoperability, and failure robustness.
We evaluate the same transactional scenarios through both USSD-style and structured tool-calling interfaces and across same- and cross-operator routes. The resulting 13,320 scored episodes reveal strong model-specific interface effects that are largely hidden by aggregate averages, identify verification-before-commit as a major source of failure, and show that cross-operator routing itself contributes comparatively little to the observed safety gap.

## Quickstart

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest -q

# Generate and validate a scenario suite (deterministic, no API calls)
momobench scenarios generate --suite smoke --seed 42
momobench scenarios validate data/scenarios/smoke

# Play a single scenario interactively
momobench play --scenario p2p_same_mtn_normal_001

# Run the free mock-agent smoke suite end to end (no API keys required)
momobench run --experiment config/experiments/smoke.yaml --agents oracle
momobench aggregate --run runs/<generated-run-dir>

# Check which configured models are reachable before spending on a real run
momobench doctor --agents config/agents.yaml
```

Real LLM provider calls require API keys and will incur provider costs — nothing in
this repository ever calls a real payment system, but the LLM API calls themselves are
real and billed once you supply credentials.

### API keys

```bash
cp .env.example .env
```

Fill in only the providers you intend to use (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`TOGETHER_API_KEY`, or `VLLM_BASE_URL`/`VLLM_API_KEY` for a self-hosted model).
`.env` is git-ignored and must never be committed.

## Repository layout

- `momobench/` — the package: `core/` (financial engine), `actions/` (agent action
  grammar), `envs/` (USSD + structured-tool interaction layers), `scenarios/` (schema,
  generator, validator), `agents/` (provider adapters + mock agents), `runner/`
  (episode and batch execution), `evaluation/` (programmatic scorer), `logging/`,
  `utils/`.
- `config/` — agent roster, benchmark/experiment configs, operator and policy
  definitions.
- `data/scenarios/` — generated scenario suites (`smoke`, `dev`, `public_test`).
- `scripts/` — CLI wrapper scripts for scenario generation/validation and running
  experiments/aggregation.
- `runs/` — experiment output (traces, results, manifests); gitignored except
  `.gitkeep`.
- `tests/` — unit and integration tests.
- `docs/` — benchmark card, scenario schema, experiment protocol, operator provenance.

## Metrics

Computed programmatically from the ledger and scenario ground truth
(`momobench.evaluation.scorer`) — never by an LLM judge: task success, safe success,
unsafe execution, correct recipient/amount, duplicate payment (+ excess amount/fee),
unnecessary refusal, recovery success, cross-operator routing error, direct unintended
financial loss, intent shortfall, valid-action rate, steps, and token usage.


## License

MIT — see `LICENSE`.
