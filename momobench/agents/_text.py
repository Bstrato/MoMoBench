"""Regex-based parsing of MoMo Bench's own deterministic observation format
(spec §29). Used only by the mock agents (NaiveAgent, RandomAgent, and the
menu-key parts of OracleAgent) — a real LLM understands the text directly;
these helpers exist so the mock agents can react to *exactly* the same text
a model would receive, never to hidden state.
"""

from __future__ import annotations

import re

_SCREEN_BODY_RE = re.compile(r"\[SCREEN\]\n(.*?)\n\n\[AVAILABLE ACTIONS\]", re.DOTALL)
_TASK_RE = re.compile(r"\[TASK\]\n(.*?)\n\n\[OPERATOR\]", re.DOTALL)
_MENU_LINE_RE = re.compile(r"^(\d+)\.\s+(.+)$", re.MULTILINE)
_ACTION_TYPE_RE = re.compile(r'"action":"(\w+)"')
_PHONE_RE = re.compile(r"\b0\d{9}\b")
_AMOUNT_RE = re.compile(r"GH₵(\d+(?:\.\d+)?)")
_HISTORY_LINE_STATUS_RE = re.compile(r"^(TX\d+)\s+GH₵\d+(?:\.\d+)?\s+(\w+)", re.MULTILINE)
_STATUS_LINE_RE = re.compile(r"^(TX\d+):\s*(\w+)\s*$", re.MULTILINE)

_SCREEN_TITLE_TAGS = {
    "Send Money": "send_menu",
    "Transfer": "send_menu",
    "Wallet": "wallet_menu",
    "Account": "wallet_menu",
    "Enter recipient number.": "enter_phone",
    "Enter Amount": "enter_amount",
    "Confirm Transaction": "preview",
    "Result": "result",
    "Transaction History": "history",
    "Transaction Status": "status",
    "Balance": "balance",
    "Not Available": "unsupported",
    "Session ended.": "terminal",
}


def latest_observation(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    raise ValueError("no observation (user-role message) found in transcript")


def instruction_text(obs: str) -> str:
    m = _TASK_RE.search(obs)
    return m.group(1).strip() if m else ""


def task_phone(obs: str) -> str | None:
    m = _PHONE_RE.search(instruction_text(obs))
    return m.group(0) if m else None


def task_amount(obs: str) -> str | None:
    m = _AMOUNT_RE.search(instruction_text(obs))
    return m.group(1) if m else None


def screen_body(obs: str) -> str:
    m = _SCREEN_BODY_RE.search(obs)
    return m.group(1) if m else ""


def screen_title(obs: str) -> str:
    body = screen_body(obs)
    return body.split("\n", 1)[0].strip() if body else ""


def classify_screen(obs: str) -> str:
    return _SCREEN_TITLE_TAGS.get(screen_title(obs), "home")


def menu_items(obs: str) -> list[tuple[str, str]]:
    return [(k, label.strip()) for k, label in _MENU_LINE_RE.findall(screen_body(obs))]


def find_menu_key(obs: str, *, contains: str | None = None, not_contains: str | None = None) -> str | None:
    for key, label in menu_items(obs):
        if contains is not None and contains.lower() not in label.lower():
            continue
        if not_contains is not None and not_contains.lower() in label.lower():
            continue
        return key
    return None


def available_action_types(obs: str) -> set[str]:
    return set(_ACTION_TYPE_RE.findall(obs))


def result_message(obs: str) -> str:
    return screen_body(obs).lower()


def last_history_status(obs: str) -> str | None:
    matches = _HISTORY_LINE_STATUS_RE.findall(screen_body(obs))
    if not matches:
        return None
    return matches[-1][1].upper()


def status_value(obs: str) -> str | None:
    m = _STATUS_LINE_RE.search(screen_body(obs))
    return m.group(2).upper() if m else None
