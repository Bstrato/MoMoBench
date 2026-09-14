#!/usr/bin/env python3
"""Thin script wrapper around `momobench scenarios validate` (spec §6).

Usage: python scripts/validate_scenarios.py data/scenarios/smoke
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from momobench.cli import scenarios_validate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    scenarios_validate(path=args.path)


if __name__ == "__main__":
    main()
