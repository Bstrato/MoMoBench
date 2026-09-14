"""MoMo Bench command-line interface.

Commands are added incrementally as each subsystem is implemented:
doctor, scenarios generate/validate, scenario show, play, run, run-one,
aggregate, report.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from momobench import BENCHMARK_VERSION, __version__
from momobench.actions.parser import parse_action
from momobench.agents.registry import is_mock_agent, load_agents_config, preflight_all
from momobench.constants import (
    AGENTS_CONFIG_PATH,
    CONFIG_DIR,
    DATA_DIR,
    DEFAULT_MAX_ACTION_TOKENS,
    DEFAULT_MAX_STEPS,
    MANIFESTS_DIR,
    POLICIES_DIR,
    REPO_ROOT,
    RUNS_DIR,
    SCENARIOS_DIR,
)
from momobench.envs.ussd import make_ussd_env
from momobench.evaluation.aggregate import (
    aggregate_by_agent,
    breakdown_by_family,
    cross_operator_generalization_gap,
)
from momobench.runner.batch import execute_run, write_results_and_aggregate
from momobench.runner.episode import run_episode
from momobench.scenarios.generator import (
    generate_extra_scenarios,
    generate_grid,
    generate_smoke_suite,
)
from momobench.scenarios.hashing import suite_manifest
from momobench.scenarios.loader import load_scenario_by_id, load_scenario_dir, save_scenario
from momobench.scenarios.validator import validate_suite

load_dotenv(REPO_ROOT / ".env")

app = typer.Typer(
    name="momobench",
    help="MoMo Bench: a stateful, consequence-aware Mobile Money agent benchmark.",
    no_args_is_help=True,
)

scenarios_app = typer.Typer(help="Generate and validate scenario suites.")
app.add_typer(scenarios_app, name="scenarios")

scenario_app = typer.Typer(help="Inspect a single scenario.")
app.add_typer(scenario_app, name="scenario")

KNOWN_SUITES = ("smoke", "dev", "public_test")


def _build_suite(suite: str) -> list:
    if suite == "smoke":
        return generate_smoke_suite()
    if suite == "dev":
        return generate_grid(seeds_per_combo=1) + generate_extra_scenarios(seeds_per_combo=1)
    if suite == "public_test":
        return generate_grid(seeds_per_combo=3) + generate_extra_scenarios(seeds_per_combo=1)
    raise typer.BadParameter(f"unknown suite {suite!r}; expected one of {KNOWN_SUITES}")


@scenarios_app.command("generate")
def scenarios_generate(
    suite: str = typer.Option(..., "--suite", help=f"One of: {', '.join(KNOWN_SUITES)}"),
    seed: int = typer.Option(42, "--seed", help="Recorded for provenance; generation is template-deterministic."),
) -> None:
    """Deterministically generate a scenario suite and write it to data/scenarios/<suite>/."""
    scenarios = _build_suite(suite)

    target_dir = SCENARIOS_DIR / suite
    target_dir.mkdir(parents=True, exist_ok=True)
    for existing in target_dir.glob("*.yaml"):
        existing.unlink()
    for s in scenarios:
        save_scenario(s, target_dir / f"{s.scenario_id}.yaml")

    manifest = suite_manifest(scenarios, suite=suite, benchmark_version=BENCHMARK_VERSION)
    manifest["generation_seed"] = seed
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MANIFESTS_DIR / f"{suite}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    typer.echo(f"generated {len(scenarios)} scenarios into {target_dir}")
    typer.echo(f"manifest written to {manifest_path}")


@scenarios_app.command("validate")
def scenarios_validate(
    path: Path = typer.Argument(..., help="Directory of scenario YAML files to validate."),
) -> None:
    """Validate every scenario in a directory (spec §42)."""
    scenarios = load_scenario_dir(path)
    if not scenarios:
        typer.echo(f"no scenario files found in {path}")
        raise typer.Exit(code=1)

    issues = validate_suite(scenarios, policies_dir=POLICIES_DIR)
    if issues:
        for issue in issues:
            typer.echo(str(issue))
        typer.echo(f"FAILED: {len(issues)} issue(s) across {len(scenarios)} scenarios in {path}")
        raise typer.Exit(code=1)

    typer.echo(f"OK: {len(scenarios)} scenarios validated, no issues found in {path}")


@scenario_app.command("show")
def scenario_show(
    scenario_id: str = typer.Argument(...),
) -> None:
    """Print the full ground-truth JSON for one scenario (for debugging; the
    agent never sees this — see `momobench play` for the agent-facing view)."""
    search_dirs = [SCENARIOS_DIR / name for name in ("smoke", "dev", "public_test", "hidden_test")]
    scenario = load_scenario_by_id(scenario_id, search_dirs)
    typer.echo(scenario.model_dump_json(indent=2))


@app.command()
def doctor(
    agents_path: Path = typer.Option(AGENTS_CONFIG_PATH, "--agents"),
) -> None:
    """Preflight every configured agent (spec §10). Never substitutes an
    unavailable model — it is reported as unavailable, with the real
    provider error, and the run manifest records the check."""
    agents_config = load_agents_config(agents_path)
    results = asyncio.run(preflight_all(agents_config))

    console = Console()
    table = Table(title="MoMo Bench Agent Preflight")
    table.add_column("Agent")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Status")
    for r in results:
        status = "[green]OK[/green]" if r.available else f"[red]UNAVAILABLE[/red] ({r.error})"
        table.add_row(r.display_name, r.provider, r.model, status)
    console.print(table)

    timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H%M%SZ")
    out_dir = RUNS_DIR / "_preflight" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "model_availability.json"
    payload = {"checked_at": timestamp, "results": [r.to_json_dict() for r in results]}
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    console.print(f"\nSaved: {out_path}")

    if any(not r.available for r in results):
        raise typer.Exit(code=1)


@app.command()
def play(
    scenario_id: str = typer.Option(..., "--scenario"),
    max_steps: int = typer.Option(DEFAULT_MAX_STEPS, "--max-steps"),
) -> None:
    """Interactively operate a scenario's USSD interface by hand (spec §81)
    — useful for debugging scenario/environment logic before involving any
    LLM. Ground truth is never shown; only the same observation an agent
    would see."""
    search_dirs = [SCENARIOS_DIR / name for name in ("smoke", "dev", "public_test", "hidden_test")]
    scenario = load_scenario_by_id(scenario_id, search_dirs)
    env = make_ussd_env(scenario.sender_operator, max_steps=max_steps)

    obs = env.reset(scenario)
    typer.echo(obs)

    while True:
        raw = typer.prompt("\nAction JSON>")
        if raw.strip().lower() in ("quit", "exit"):
            typer.echo("(exiting without finishing the episode)")
            break

        parsed = parse_action(raw)
        if not parsed.ok:
            typer.echo(f"\n{parsed.error}")
            continue

        result = env.step(parsed.action)
        typer.echo("\n" + result.observation)

        if result.terminated or result.truncated:
            typer.echo(f"\n(episode ended: terminated={result.terminated} truncated={result.truncated})")
            break


@app.command()
def run(
    experiment: Path = typer.Option(..., "--experiment"),
    resume: bool = typer.Option(False, "--resume"),
    run_dir: Path | None = typer.Option(None, "--run-dir", help="Required when --resume is set."),
    agents: str | None = typer.Option(
        None, "--agents", help="Comma-separated agent keys, overriding the experiment config's list."
    ),
    agents_path: Path = typer.Option(AGENTS_CONFIG_PATH, "--agents-config"),
) -> None:
    """Run a batch experiment (spec §55-57). Every episode gets a fresh
    isolated MoMoWorld; real-provider episodes are wrapped with transport
    retries. Resumable via --resume (pass the same --run-dir back in)."""
    if resume and run_dir is None:
        typer.echo("--resume requires --run-dir pointing at the run to resume")
        raise typer.Exit(code=1)

    if agents is not None:
        import yaml

        data = yaml.safe_load(Path(experiment).read_text(encoding="utf-8"))
        data["agents"] = [a.strip() for a in agents.split(",") if a.strip()]
        tmp_path = Path(experiment).with_suffix(".override.yaml")
        tmp_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        experiment_to_run = tmp_path
    else:
        experiment_to_run = experiment

    try:
        out_dir = execute_run(
            experiment_to_run, run_dir=run_dir, resume=resume, agents_config_path=agents_path
        )
    finally:
        if agents is not None:
            tmp_path.unlink(missing_ok=True)

    typer.echo(f"run complete: {out_dir}")


@app.command("run-one")
def run_one(
    agent: str = typer.Option(..., "--agent"),
    scenario_id: str = typer.Option(..., "--scenario"),
    interface: str = typer.Option("ussd", "--interface"),
    max_steps: int = typer.Option(DEFAULT_MAX_STEPS, "--max-steps"),
    max_action_tokens: int = typer.Option(DEFAULT_MAX_ACTION_TOKENS, "--max-action-tokens"),
    agents_path: Path = typer.Option(AGENTS_CONFIG_PATH, "--agents-config"),
) -> None:
    """Run exactly one episode and print its score — the fastest way to
    sanity-check a scenario/agent pairing (spec §122) before a full batch."""
    from momobench.agents.registry import get_agent_factory
    from momobench.envs import make_env

    search_dirs = [SCENARIOS_DIR / name for name in ("smoke", "dev", "public_test", "hidden_test")]
    scenario = load_scenario_by_id(scenario_id, search_dirs)

    agents_config = {} if is_mock_agent(agent) else load_agents_config(agents_path)
    factory = get_agent_factory(agent, agents_config)
    agent_instance = factory(scenario)

    env = make_env(interface, scenario.sender_operator, max_steps=max_steps)

    result = asyncio.run(
        run_episode(agent_instance, env, scenario, max_steps=max_steps, max_action_tokens=max_action_tokens)
    )

    typer.echo(json.dumps(result.score.to_json_dict(), indent=2, default=str))
    typer.echo(f"\nsteps={result.total_turns} format_errors={result.format_errors} "
               f"terminated={result.terminated} truncated={result.truncated}")


@app.command()
def aggregate(
    run: Path = typer.Option(..., "--run", help="A run directory (containing results.csv)."),
) -> None:
    """Recompute aggregate tables from an existing run's results.csv (spec
    §73, §89)."""
    results_path = run / "results.csv"
    if not results_path.exists():
        typer.echo(f"no results.csv found in {run}")
        raise typer.Exit(code=1)

    df = pd.read_csv(results_path)
    write_results_and_aggregate(run, df.to_dict(orient="records"))

    console = Console()
    scored = df[df.get("episode_status", "OK") == "OK"] if "episode_status" in df else df
    if len(scored):
        console.print(aggregate_by_agent(scored))
    typer.echo(f"\naggregate.json / results.csv / results.parquet / failures.csv refreshed in {run}")


@app.command()
def report(
    run: Path = typer.Option(..., "--run", help="A run directory (containing results.csv)."),
) -> None:
    """Print a readable summary report for a run: per-agent metrics,
    per-family breakdown, and the same-vs-cross-operator generalization
    gap (spec §74)."""
    results_path = run / "results.csv"
    if not results_path.exists():
        typer.echo(f"no results.csv found in {run}")
        raise typer.Exit(code=1)

    df = pd.read_csv(results_path)
    scored = df[df.get("episode_status", "OK") == "OK"] if "episode_status" in df else df
    if not len(scored):
        typer.echo("no scored episodes to report on")
        raise typer.Exit(code=1)

    console = Console()
    console.rule("Per-agent summary")
    console.print(aggregate_by_agent(scored))

    if "family" in scored.columns:
        console.rule("Per-family breakdown")
        console.print(breakdown_by_family(scored))

    if {"sender_operator", "receiver_operator"}.issubset(scored.columns):
        console.rule("Cross-operator generalization gap")
        console.print(cross_operator_generalization_gap(scored))


@app.command()
def version() -> None:
    """Print the installed MoMo Bench version."""
    typer.echo(f"momobench {__version__}")


@app.command()
def info() -> None:
    """Print resolved repository paths (useful for sanity-checking an install)."""
    typer.echo(f"momobench {__version__}")
    typer.echo(f"repo root : {REPO_ROOT}")
    typer.echo(f"config dir: {CONFIG_DIR}")
    typer.echo(f"data dir  : {DATA_DIR}")
    typer.echo(f"runs dir  : {RUNS_DIR}")


if __name__ == "__main__":
    app()
