#!/usr/bin/env python3
"""Thin script wrapper around `momobench scenarios generate` (spec §6).

Usage: python scripts/generate_scenarios.py --suite smoke --seed 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from momobench.cli import scenarios_generate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, choices=["smoke", "dev", "public_test"])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    scenarios_generate(suite=args.suite, seed=args.seed)


if __name__ == "__main__":
    main()
