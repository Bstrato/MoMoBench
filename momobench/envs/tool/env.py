"""Structured tool environment (spec §100). The same ``MoMoWorld`` as the
USSD interface — only the interaction layer differs, from menu navigation
to direct tool calls (get_balance, resolve_recipient, prepare_transfer,
confirm_transfer, cancel_transfer, get_transaction_status,
get_transaction_history). Useful for separating financial reasoning from
USSD navigation difficulty (spec §101): the same scenario can be evaluated
through both interfaces and compared.
"""

from __future__ import annotations

import json
from pathlib import Path

from momobench.constants import DEFAULT_MAX_STEPS, POLICIES_DIR
from momobench.core.models import query_visible_status
from momobench.core.world import MoMoWorld, create_world
from momobench.envs.base import BaseMoMoEnv, StepResult
from momobench.envs.tool.schema import ToolAction
from momobench.utils.money import InvalidMoneyError, money

TOOL_NAMES = (
    "get_balance",
    "resolve_recipient",
    "prepare_transfer",
    "confirm_transfer",
    "cancel_transfer",
    "get_transaction_status",
    "get_transaction_history",
    "wait",
    "finish",
)

# The literal 'arguments' shape _dispatch() reads for each tool — rendered
# into the observation so the agent never has to guess argument names (spec
# §100). Mirrors how the USSD interface shows a literal JSON action
# template via AvailableAction.render() rather than a bare action name.
TOOL_ARGUMENT_TEMPLATES: dict[str, dict[str, str]] = {
    "get_balance": {},
    "resolve_recipient": {"phone": "<recipient phone number>"},
    "prepare_transfer": {"phone": "<recipient phone number>", "amount": "<amount>"},
    "confirm_transfer": {},
    "cancel_transfer": {},
    "get_transaction_status": {"transaction_id": "<transaction id, optional: defaults to the most recent>"},
    "get_transaction_history": {},
    "wait": {},
    "finish": {},
}


def _render_tool_call_template(tool: str) -> str:
    arguments = TOOL_ARGUMENT_TEMPLATES[tool]
    args_json = json.dumps(arguments)
    return f'{{"tool":"{tool}","arguments":{args_json}}}'


class ToolEnv(BaseMoMoEnv):
    def __init__(self, *, max_steps: int = DEFAULT_MAX_STEPS, policies_dir: str | Path = POLICIES_DIR) -> None:
        self.max_steps = max_steps
        self.policies_dir = policies_dir

        self.world: MoMoWorld | None = None
        self.scenario = None
        self.sender_wallet_id: str | None = None
        self.pending_preview = None
        self.last_tx_id: str | None = None

        self.step_count = 0
        self.terminated = False
        self.truncated = False
        self._last_observation = ""

    def reset(self, scenario) -> str:
        self.world = create_world(scenario, self.policies_dir)
        self.scenario = scenario
        self.sender_wallet_id = f"w_{scenario.goal.sender_user_id}"
        self.pending_preview = None
        self.last_tx_id = None
        self.step_count = 0
        self.terminated = False
        self.truncated = False
        self._last_observation = self._render(message=None)
        return self._last_observation

    def render(self) -> str:
        return self._last_observation

    def step(self, action: ToolAction) -> StepResult:
        if self.terminated or self.truncated:
            raise RuntimeError("step() called on an already-finished episode")

        self.step_count += 1
        self.world.advance_time(1)
        info: dict = {"tool": action.tool, "arguments": dict(action.arguments)}

        message = self._dispatch(action, info)

        if self.step_count >= self.max_steps and not self.terminated:
            self.truncated = True

        self._last_observation = self._render(message=message)
        return StepResult(
            observation=self._last_observation, terminated=self.terminated, truncated=self.truncated, info=info
        )

    def _dispatch(self, action: ToolAction, info: dict) -> str:
        args = action.arguments

        if action.tool == "finish":
            self.terminated = True
            return "Session ended."

        if action.tool == "wait":
            return "Waited one step."

        if action.tool == "get_balance":
            return f"balance: GH₵{self.world.get_balance(self.sender_wallet_id)}"

        if action.tool == "resolve_recipient":
            phone = args.get("phone")
            recipient = self.world.resolve_recipient(phone) if phone else None
            if recipient is None:
                return "No account found for this number."
            return f"name: {recipient.name}, operator: {recipient.operator.value}"

        if action.tool == "prepare_transfer":
            phone = args.get("phone")
            raw_amount = args.get("amount")
            if not phone or raw_amount is None:
                return "prepare_transfer requires 'phone' and 'amount' arguments."
            try:
                amount = money(raw_amount)
            except InvalidMoneyError:
                self.pending_preview = None
                return f"invalid amount: {raw_amount!r}"

            preview = self.world.preview_transfer(self.sender_wallet_id, phone, amount)
            self.pending_preview = preview
            if not preview.can_execute:
                return f"cannot execute: {preview.blocking_reason}"
            return (
                f"recipient: {preview.recipient_name}, operator: {preview.receiver_operator.value}, "
                f"amount: GH₵{preview.amount}, fee: GH₵{preview.fee}, total_debit: GH₵{preview.total_debit}"
            )

        if action.tool == "confirm_transfer":
            if self.pending_preview is None or not self.pending_preview.can_execute:
                return "No executable prepared transfer to confirm."
            tx = self.world.commit_transfer(self.pending_preview)
            self.pending_preview = None
            self.last_tx_id = tx.id
            info["transaction_id"] = tx.id
            info["ledger_status"] = tx.ledger_status.value
            info["visible_status"] = tx.visible_status.value
            return f"transaction_id: {tx.id}, status: {tx.visible_status.value}"

        if action.tool == "cancel_transfer":
            self.pending_preview = None
            return "Prepared transfer cancelled."

        if action.tool == "get_transaction_status":
            tx_id = args.get("transaction_id") or self.last_tx_id
            if tx_id is None:
                return "No transaction to check yet."
            try:
                tx = self.world.transaction_status(tx_id)
            except Exception:  # noqa: BLE001 - unknown tx id is expected input, not a bug
                return "Transaction not found."
            return f"{tx.id}: {query_visible_status(tx).value}"

        if action.tool == "get_transaction_history":
            history = self.world.transaction_history(self.sender_wallet_id)
            if not history:
                return "No transactions yet."
            return "; ".join(f"{tx.id} GH₵{tx.amount} {query_visible_status(tx).value}" for tx in history)

        return "Unknown tool."

    def _render(self, *, message: str | None) -> str:
        lines = ["[TASK]", self.scenario.instruction, "", "[AVAILABLE TOOLS]"]
        lines.extend(_render_tool_call_template(name) for name in TOOL_NAMES)
        if message is not None:
            lines.append("")
            lines.append("[RESULT]")
            lines.append(message)
        lines.append("")
        lines.append("[STEP]")
        lines.append(f"{self.step_count} / {self.max_steps}")
        return "\n".join(lines)
