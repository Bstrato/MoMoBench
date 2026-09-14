#!/usr/bin/env python3
"""Thin script wrapper around `momobench aggregate` (spec §6).

Usage: python scripts/aggregate_results.py --run runs/<run-dir>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from momobench.evaluation.aggregate import aggregate_by_agent
from momobench.runner.batch import write_results_and_aggregate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()

    results_path = args.run / "results.csv"
    if not results_path.exists():
        raise SystemExit(f"no results.csv found in {args.run}")

    df = pd.read_csv(results_path)
    write_results_and_aggregate(args.run, df.to_dict(orient="records"))

    scored = df[df.get("episode_status", "OK") == "OK"] if "episode_status" in df else df
    if len(scored):
        print(aggregate_by_agent(scored).to_string())
    print(f"\naggregate.json / results.csv / results.parquet / failures.csv refreshed in {args.run}")


if __name__ == "__main__":
    main()
