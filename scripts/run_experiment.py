#!/usr/bin/env python3
"""Thin script wrapper around `momobench run` (spec §6).

Usage: python scripts/run_experiment.py --experiment config/experiments/smoke.yaml [--resume --run-dir <dir>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from momobench.constants import AGENTS_CONFIG_PATH
from momobench.runner.batch import execute_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--agents-config", type=Path, default=AGENTS_CONFIG_PATH)
    args = parser.parse_args()

    if args.resume and args.run_dir is None:
        parser.error("--resume requires --run-dir")

    out_dir = execute_run(
        args.experiment, run_dir=args.run_dir, resume=args.resume, agents_config_path=args.agents_config
    )
    print(f"run complete: {out_dir}")


if __name__ == "__main__":
    main()
