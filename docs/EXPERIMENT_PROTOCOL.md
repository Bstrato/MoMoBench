# Experiment Protocol

## Staged rollout (spec §78)

1. **Smoke** (`config/experiments/smoke.yaml`) — 12 hand-reviewed scenarios
   against the mock-agent controls (`oracle`, `naive`, `random`) only. No
   API keys, no cost. Run first, always: `momobench run --experiment
   config/experiments/smoke.yaml`.
2. **Pilot** (`config/experiments/pilot.yaml`) — all 14 configured real
   models, 1 repeat, against `data/scenarios/dev` (78 scenarios). Requires
   API keys and incurs real provider cost. Use it to catch prompt-format
   failures, impossible scenarios, scoring bugs, and rate-limit issues
   before committing to the final run.
3. **Frozen final core** (`config/experiments/final_core.yaml`) — the same
   14 models, 3 repeats, against the frozen `data/scenarios/public_test`
   suite (222 scenarios). Do not edit scenarios after this stage begins;
   any change requires a new `benchmark_version`.
4. **Cross-operator focus** (`config/experiments/cross_operator.yaml`) — a
   `require_tags: [cross_operator]` filter over the same suite, for a
   homogeneous same-vs-cross comparison slice.

## Before spending money

1. `momobench doctor --agents config/agents.yaml` — confirms every
   configured model is reachable under the current API keys. An
   unavailable model is reported as such and the experiment for that agent
   should not proceed silently substituted (spec §119).
2. Inspect pilot traces (`runs/<pilot-run>/episodes/*/*/transcript.txt`) to
   estimate average turns and tokens per episode before estimating final
   cost (spec §94). `momobench estimate` is not yet implemented — compute
   this manually from `results.csv` in the interim
   (`mean(steps)`, `mean(input_tokens)`, `mean(output_tokens)`).

## Fairness rules (do not change without updating this document)

- One common system prompt (`momobench.agents.prompts.COMMON_SYSTEM_PROMPT`)
  for every model; its hash is recorded in every run manifest.
- No temperature/top_p/reasoning-effort overrides — provider/model
  defaults only, so cross-provider comparison isn't confounded by
  per-model sampling tuning.
- Transport retries (429/5xx/timeout/connection) resend the identical
  request; a malformed or unsafe *decision* is never retried at this layer
  — it is scored as agent behavior.
- Repeats: 1 for smoke/pilot/dev work, 3 for the frozen final run
  (`repeat_id` recorded per episode).

## Reproducibility checklist (spec §120)

Archive alongside any published result: the git commit/tag
(`manifest.json["git_commit"]`), `config/agents.yaml`,
`config/benchmark.yaml`, the experiment config used, the system prompt hash,
the scenario suite + its content-hash manifest
(`data/manifests/<suite>.json`), the fee/limits policy files, the interface
profile ID, the `doctor` preflight output, installed package versions
(`manifest.json["package_versions"]`), raw episode traces
(`episodes/*/*/trace.jsonl`), `result.json` files, and
`results.csv`/`results.parquet`/`aggregate.json`.

## Resuming an interrupted run

`momobench run --experiment <cfg> --resume --run-dir <existing run dir>`.
A completed, valid `result.json` is never overwritten; missing/invalid ones
are recomputed. Without `--resume`, every episode is recomputed.
