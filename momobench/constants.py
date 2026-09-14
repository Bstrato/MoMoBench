"""Repository-wide path and default constants."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"
MANIFESTS_DIR = DATA_DIR / "manifests"
RUNS_DIR = REPO_ROOT / "runs"

AGENTS_CONFIG_PATH = CONFIG_DIR / "agents.yaml"
BENCHMARK_CONFIG_PATH = CONFIG_DIR / "benchmark.yaml"
EXPERIMENTS_DIR = CONFIG_DIR / "experiments"
OPERATORS_DIR = CONFIG_DIR / "operators"
POLICIES_DIR = CONFIG_DIR / "policies"

DEFAULT_FEE_POLICY_ID = "synthetic_fee_v1"
DEFAULT_LIMITS_POLICY_ID = "synthetic_limits_v1"
DEFAULT_INTERFACE_PROFILE_ID = "normalized_v1"

DEFAULT_MAX_STEPS = 20
DEFAULT_MAX_ACTION_TOKENS = 128

CURRENCY_SYMBOL = "GH₵"
CURRENCY_CODE = "GHS"
