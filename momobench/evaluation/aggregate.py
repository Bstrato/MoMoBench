"""Aggregate per-episode result rows into summary tables (spec §73, §89,
§74). Operates on plain dicts / a pandas DataFrame of one row per episode —
each row is expected to carry both the ``EpisodeScore`` fields and enough
scenario metadata (agent_key, family, sender_operator, receiver_operator,
route, ported) to support the breakdowns below. Nothing here recomputes
outcomes — that's the scorer's job; this module only summarizes."""

from __future__ import annotations

import math

import pandas as pd

RATE_COLUMNS = [
    "task_success",
    "safe_success",
    "unsafe_execution",
    "duplicate_payment",
    "unnecessary_refusal",
]


def episodes_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _rate(series: pd.Series) -> float:
    if len(series) == 0:
        return float("nan")
    return float(series.mean())


def _optional_rate(series: pd.Series) -> float:
    """Mean over non-null values only (routing_error / recovery_success are
    None for episodes where the metric doesn't apply)."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return float("nan")
    return float(non_null.astype(bool).mean())


def summarize(df: pd.DataFrame) -> dict:
    """One flat summary dict for a (possibly already-filtered) slice of
    episodes — the row shape used by every breakdown table below."""
    n = len(df)
    out = {
        "n_episodes": n,
        "task_success_rate": _rate(df["task_success"]) if n else float("nan"),
        "safe_success_rate": _rate(df["safe_success"]) if n else float("nan"),
        "unsafe_execution_rate": _rate(df["unsafe_execution"]) if n else float("nan"),
        "wrong_recipient_rate": 1.0 - _rate(df["correct_recipient"]) if n else float("nan"),
        "wrong_amount_rate": 1.0 - _rate(df["correct_amount"]) if n else float("nan"),
        "duplicate_payment_rate": _rate(df["duplicate_payment"]) if n else float("nan"),
        "unnecessary_refusal_rate": _rate(df["unnecessary_refusal"]) if n else float("nan"),
        "recovery_success_rate": _optional_rate(df["recovery_success"]) if n else float("nan"),
        "routing_error_rate": _optional_rate(df["routing_error"]) if n else float("nan"),
        "mean_direct_financial_loss": float(df["direct_unintended_loss"].astype(float).mean()) if n else 0.0,
        "median_direct_financial_loss": float(df["direct_unintended_loss"].astype(float).median()) if n else 0.0,
        "total_direct_financial_loss": float(df["direct_unintended_loss"].astype(float).sum()) if n else 0.0,
        "mean_intent_shortfall": float(df["intent_shortfall"].astype(float).mean()) if n else 0.0,
        "mean_steps": float(df["steps"].mean()) if n and "steps" in df else float("nan"),
    }
    if "format_errors" in df and "steps" in df and n:
        total_steps = df["steps"].sum()
        total_format_errors = df["format_errors"].sum()
        out["valid_action_rate"] = (
            1.0 - (total_format_errors / total_steps) if total_steps > 0 else float("nan")
        )
    if "input_tokens" in df and n:
        out["mean_input_tokens"] = float(df["input_tokens"].mean())
    if "output_tokens" in df and n:
        out["mean_output_tokens"] = float(df["output_tokens"].mean())
    return out


def aggregate_by_agent(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for agent_key, group in df.groupby("agent_key"):
        row = {"agent_key": agent_key, **summarize(group)}
        rows.append(row)
    return pd.DataFrame(rows).sort_values("agent_key").reset_index(drop=True)


def _breakdown(df: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    cols = by if isinstance(by, list) else [by]
    rows = []
    for key, group in df.groupby(cols):
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = dict(zip(cols, key_tuple))
        row.update(summarize(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(cols).reset_index(drop=True)


def breakdown_by_family(df: pd.DataFrame) -> pd.DataFrame:
    return _breakdown(df, ["agent_key", "family"])


def breakdown_by_route(df: pd.DataFrame) -> pd.DataFrame:
    return _breakdown(df, ["agent_key", "sender_operator", "receiver_operator"])


def breakdown_by_same_vs_cross(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["route_type"] = df.apply(
        lambda r: "same_operator" if r["sender_operator"] == r["receiver_operator"] else "cross_operator",
        axis=1,
    )
    return _breakdown(df, ["agent_key", "route_type"])


def breakdown_by_difficulty(df: pd.DataFrame) -> pd.DataFrame:
    return _breakdown(df, ["agent_key", "difficulty"])


def breakdown_by_failure_mode(df: pd.DataFrame) -> pd.DataFrame:
    return _breakdown(df, ["agent_key", "failure_mode"])


def breakdown_by_ported(df: pd.DataFrame) -> pd.DataFrame:
    return _breakdown(df, ["agent_key", "ported"])


def cross_operator_generalization_gap(df: pd.DataFrame) -> pd.DataFrame:
    """spec §74: Delta_op = SR_same - SR_cross (safe success rate), per agent."""
    same_cross = breakdown_by_same_vs_cross(df)
    rows = []
    for agent_key, group in same_cross.groupby("agent_key"):
        same = group[group["route_type"] == "same_operator"]["safe_success_rate"]
        cross = group[group["route_type"] == "cross_operator"]["safe_success_rate"]
        sr_same = float(same.iloc[0]) if len(same) else float("nan")
        sr_cross = float(cross.iloc[0]) if len(cross) else float("nan")
        both_defined = not (math.isnan(sr_same) or math.isnan(sr_cross))
        rows.append(
            {
                "agent_key": agent_key,
                "sr_same": sr_same,
                "sr_cross": sr_cross,
                "delta_operator": sr_same - sr_cross if both_defined else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values("agent_key").reset_index(drop=True)


def matched_group_paired_scores(df: pd.DataFrame) -> pd.DataFrame:
    """spec §74: for each match_group_id, the per-route safe_success used
    for paired (not merely aggregate) same-vs-cross comparison."""
    if "match_group_id" not in df.columns:
        return pd.DataFrame()
    cols = ["agent_key", "match_group_id", "sender_operator", "receiver_operator", "safe_success"]
    return df[[c for c in cols if c in df.columns]].sort_values(["agent_key", "match_group_id"]).reset_index(drop=True)
