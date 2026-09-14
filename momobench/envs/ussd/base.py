"""Shared, deterministic USSD state machine (spec §31-32). Provider
subclasses (MTN/Telecel/AT) supply only a menu-label configuration; every
financial call goes through the same ``MoMoWorld`` instance, so wallet
debit/credit semantics are never duplicated per provider (spec §5.5).

Transitions are driven purely by (current ScreenState, AgentAction) — never
by parsing free-form text — so the machine is fully deterministic (spec
§31).
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from pathlib import Path

from momobench.actions.schema import AgentAction
from momobench.constants import DEFAULT_MAX_STEPS, POLICIES_DIR
from momobench.core.models import Operator, VisibleStatus, query_visible_status
from momobench.core.world import MoMoWorld, create_world
from momobench.envs.base import BaseMoMoEnv, StepResult
from momobench.envs.observation import AvailableAction, render_observation
from momobench.utils.io import load_yaml
from momobench.utils.money import InvalidMoneyError, money


class ScreenState(str, Enum):
    HOME = "home"
    SEND_MENU = "send_menu"
    DESTINATION_MENU = "destination_menu"  # reserved; unused in the normalized_v1 profile
    ENTER_PHONE = "enter_phone"
    ENTER_AMOUNT = "enter_amount"
    PREVIEW = "preview"
    SUBMITTING = "submitting"  # transient; commit is synchronous within the confirm step
    RESULT = "result"
    HISTORY = "history"
    STATUS = "status"
    WALLET_MENU = "wallet_menu"
    BALANCE = "balance"
    UNSUPPORTED = "unsupported"
    TERMINAL = "terminal"


_OPERATOR_DISPLAY = {
    Operator.MTN: "MTN",
    Operator.TELECEL: "Telecel",
    Operator.AT: "AT",
}


class BaseUSSDEnv(BaseMoMoEnv):
    """Shared logic for every provider's USSD interface. Subclasses set
    ``operator`` and ``config_path`` (a YAML file under config/operators/)."""

    operator: Operator
    config_path: Path

    def __init__(self, *, max_steps: int = DEFAULT_MAX_STEPS, policies_dir: str | Path = POLICIES_DIR) -> None:
        self.max_steps = max_steps
        self.policies_dir = policies_dir
        self.config: dict = load_yaml(self.config_path)

        self.world: MoMoWorld | None = None
        self.scenario = None
        self.sender_wallet_id: str | None = None

        self.state = ScreenState.HOME
        self.declared_route: str | None = None
        self.pending_phone: str | None = None
        self.pending_recipient = None
        self.pending_preview = None
        self.last_tx_id: str | None = None
        self.pending_error: str | None = None
        self.last_result_message: str | None = None
        self.status_query_tx_id: str | None = None

        self.step_count = 0
        self.terminated = False
        self.truncated = False
        self._last_observation = ""
        self.initial_snapshot = None

    # -- lifecycle --------------------------------------------------------

    def reset(self, scenario) -> str:
        self.world = create_world(scenario, self.policies_dir)
        self.scenario = scenario
        self.sender_wallet_id = f"w_{scenario.goal.sender_user_id}"
        self.initial_snapshot = self.world.initial_snapshot

        self.state = ScreenState.HOME
        self.declared_route = None
        self.pending_phone = None
        self.pending_recipient = None
        self.pending_preview = None
        self.last_tx_id = None
        self.pending_error = None
        self.last_result_message = None
        self.status_query_tx_id = None

        self.step_count = 0
        self.terminated = False
        self.truncated = False

        self._last_observation = self._render()
        return self._last_observation

    def render(self) -> str:
        return self._last_observation

    # -- step ---------------------------------------------------------------

    def step(self, action: AgentAction) -> StepResult:
        if self.terminated or self.truncated:
            raise RuntimeError("step() called on an already-finished episode")

        self.step_count += 1
        self.world.advance_time(1)

        info: dict = {"state_before": self.state.value, "action": action.action, "value": action.value}
        self.pending_error = None

        valid = self._dispatch(action, info)
        info["valid_action"] = valid
        if not valid and self.pending_error is None:
            self.pending_error = "That action is not available on this screen."

        if self.step_count >= self.max_steps and not self.terminated:
            self.truncated = True

        self._last_observation = self._render()
        return StepResult(
            observation=self._last_observation,
            terminated=self.terminated,
            truncated=self.truncated,
            info=info,
        )

    # -- dispatch -----------------------------------------------------------

    def _dispatch(self, action: AgentAction, info: dict) -> bool:
        act = action.action

        if act == "finish":
            self.terminated = True
            self.state = ScreenState.TERMINAL
            return True

        if act == "wait":
            return True  # the clock already ticked once above; nothing else to do

        if act == "check_history":
            self.state = ScreenState.HISTORY
            return True

        if act == "check_status":
            tx_id = action.value or self.last_tx_id
            if tx_id is None:
                self.pending_error = "No transaction to check yet."
                return False
            self.status_query_tx_id = tx_id
            self.state = ScreenState.STATUS
            return True

        if act == "back":
            return self._handle_back()

        if act == "select":
            return self._handle_select(action.value, info)

        if act == "enter":
            return self._handle_enter(action.value, info)

        if act == "confirm":
            return self._handle_confirm(info)

        if act == "cancel":
            return self._handle_cancel()

        return False

    def _handle_back(self) -> bool:
        parent = {
            ScreenState.SEND_MENU: ScreenState.HOME,
            ScreenState.WALLET_MENU: ScreenState.HOME,
            ScreenState.ENTER_PHONE: ScreenState.SEND_MENU,
            ScreenState.ENTER_AMOUNT: ScreenState.ENTER_PHONE,
            ScreenState.PREVIEW: ScreenState.ENTER_AMOUNT,
            ScreenState.RESULT: ScreenState.HOME,
            ScreenState.HISTORY: ScreenState.HOME,
            ScreenState.STATUS: ScreenState.HOME,
            ScreenState.BALANCE: ScreenState.HOME,
            ScreenState.UNSUPPORTED: ScreenState.HOME,
        }.get(self.state)
        if parent is None:
            self.pending_error = "There is nowhere to go back to."
            return False
        self.state = parent
        return True

    def _handle_select(self, value: str | None, info: dict) -> bool:
        if self.state == ScreenState.HOME:
            item = self._find_menu_item(self.config["home_menu"], value)
            if item is None:
                self.pending_error = "Invalid option."
                return False
            leads_to = item["leads_to"]
            if leads_to == "send_menu":
                self.state = ScreenState.SEND_MENU
            elif leads_to == "wallet_menu":
                self.state = ScreenState.WALLET_MENU
            else:
                self.state = ScreenState.UNSUPPORTED
            return True

        if self.state == ScreenState.SEND_MENU:
            item = self._find_menu_item(self.config["send_menu"], value)
            if item is None:
                self.pending_error = "Invalid option."
                return False
            if item["leads_to"] == "home":
                self.state = ScreenState.HOME
                return True
            self.declared_route = item.get("route")
            self.state = ScreenState.ENTER_PHONE
            return True

        if self.state == ScreenState.WALLET_MENU:
            item = self._find_menu_item(self.config["wallet_menu"], value)
            if item is None:
                self.pending_error = "Invalid option."
                return False
            if item["leads_to"] == "balance":
                self.state = ScreenState.BALANCE
            elif item["leads_to"] == "history":
                self.state = ScreenState.HISTORY
            else:
                self.state = ScreenState.HOME
            return True

        self.pending_error = "That action is not available on this screen."
        return False

    def _handle_enter(self, value: str | None, info: dict) -> bool:
        if value is None or value == "":
            self.pending_error = "Please provide a value."
            return False

        if self.state == ScreenState.ENTER_PHONE:
            recipient = self.world.resolve_recipient(value)
            if recipient is None:
                self.pending_error = "No account found for this number."
                return False
            self.pending_phone = value
            self.pending_recipient = recipient
            resolved_route = "same_operator" if recipient.operator == self.operator else "cross_operator"
            info["declared_route"] = self.declared_route
            info["resolved_route"] = resolved_route
            info["route_mismatch"] = bool(
                self.declared_route is not None and self.declared_route != resolved_route
            )
            self.state = ScreenState.ENTER_AMOUNT
            return True

        if self.state == ScreenState.ENTER_AMOUNT:
            try:
                amount = money(value)
            except InvalidMoneyError:
                self.pending_error = "Enter a valid amount."
                return False
            if amount <= Decimal("0.00"):
                self.pending_error = "Enter an amount greater than zero."
                return False
            self.pending_preview = self.world.preview_transfer(self.sender_wallet_id, self.pending_phone, amount)
            self.state = ScreenState.PREVIEW
            return True

        self.pending_error = "That action is not available on this screen."
        return False

    def _handle_confirm(self, info: dict) -> bool:
        if self.state != ScreenState.PREVIEW or self.pending_preview is None:
            self.pending_error = "That action is not available on this screen."
            return False
        if not self.pending_preview.can_execute:
            self.pending_error = self.pending_preview.blocking_reason
            return False

        tx = self.world.commit_transfer(self.pending_preview)
        self.last_tx_id = tx.id
        info["transaction_id"] = tx.id
        info["ledger_status"] = tx.ledger_status.value
        info["visible_status"] = tx.visible_status.value

        self.last_result_message = self._visible_result_message(tx.visible_status, tx.id)
        self.state = ScreenState.RESULT
        return True

    def _handle_cancel(self) -> bool:
        if self.state != ScreenState.PREVIEW:
            self.pending_error = "That action is not available on this screen."
            return False
        self.last_result_message = "Transaction cancelled."
        self.pending_preview = None
        self.state = ScreenState.RESULT
        return True

    @staticmethod
    def _visible_result_message(visible_status: VisibleStatus, tx_id: str) -> str:
        if visible_status == VisibleStatus.SUCCESS:
            return f"Transaction successful.\nReference: {tx_id}"
        if visible_status == VisibleStatus.FAILED:
            return "Transaction failed. Please try again."
        if visible_status == VisibleStatus.PENDING:
            return "Transaction pending. Please check status shortly."
        if visible_status == VisibleStatus.UNKNOWN:
            return "Request timed out. The transaction outcome is unknown."
        return "Transaction submitted."

    @staticmethod
    def _find_menu_item(menu: list[dict], value: str | None) -> dict | None:
        if value is None:
            return None
        for item in menu:
            if item["key"] == value:
                return item
        return None

    # -- rendering ------------------------------------------------------

    def _global_actions(self) -> list[AvailableAction]:
        actions = [AvailableAction("finish")]
        actions.append(AvailableAction("check_history"))
        if self.last_tx_id is not None:
            actions.append(AvailableAction("check_status", self.last_tx_id))
        actions.append(AvailableAction("wait"))
        return actions

    def _back_action(self) -> list[AvailableAction]:
        return [] if self.state == ScreenState.HOME else [AvailableAction("back")]

    def _render(self) -> str:
        title, body = self._render_screen()
        state_actions = self._render_state_actions()
        actions = state_actions + self._back_action() + self._global_actions()

        return render_observation(
            task=self.scenario.instruction,
            operator_display_name=self.config["display_name"],
            screen_title=title,
            screen_body=body,
            actions=actions,
            step=self.step_count,
            max_steps=self.max_steps,
            error=self.pending_error,
        )

    def _render_state_actions(self) -> list[AvailableAction]:
        if self.state == ScreenState.HOME:
            return [AvailableAction("select", "<menu option number, e.g. \\\"1\\\">")]
        if self.state in (ScreenState.SEND_MENU, ScreenState.WALLET_MENU):
            return [AvailableAction("select", "<menu option number, e.g. \\\"1\\\">")]
        if self.state == ScreenState.ENTER_PHONE:
            return [AvailableAction("enter", "<recipient phone number>")]
        if self.state == ScreenState.ENTER_AMOUNT:
            return [AvailableAction("enter", "<amount>")]
        if self.state == ScreenState.PREVIEW:
            if self.pending_preview is not None and self.pending_preview.can_execute:
                return [AvailableAction("confirm"), AvailableAction("cancel")]
            return [AvailableAction("cancel")]
        return []

    def _render_screen(self) -> tuple[str, list[str]]:
        cfg = self.config

        if self.state == ScreenState.HOME:
            body = [f"{i['key']}. {i['label']}" for i in cfg["home_menu"]]
            return cfg["home_title"], body

        if self.state == ScreenState.SEND_MENU:
            body = [f"{i['key']}. {i['label']}" for i in cfg["send_menu"]]
            return cfg["send_menu_title"], body

        if self.state == ScreenState.WALLET_MENU:
            body = [f"{i['key']}. {i['label']}" for i in cfg["wallet_menu"]]
            return cfg["wallet_menu_title"], body

        if self.state == ScreenState.ENTER_PHONE:
            return "Enter recipient number.", []

        if self.state == ScreenState.ENTER_AMOUNT:
            body = [
                f"Recipient: {self.pending_recipient.name.upper()}",
                f"Current network: {_OPERATOR_DISPLAY[self.pending_recipient.operator]}",
                "",
                "Enter amount.",
            ]
            return "Enter Amount", body

        if self.state == ScreenState.PREVIEW:
            p = self.pending_preview
            if p.can_execute:
                body = [
                    f"Send GH₵{p.amount} to {p.recipient_name.upper()}",
                    f"Network: {_OPERATOR_DISPLAY[p.receiver_operator]}",
                    f"Fee: GH₵{p.fee}",
                    f"Total debit: GH₵{p.total_debit}",
                    "",
                    "1. Confirm",
                    "2. Cancel",
                ]
            else:
                body = [
                    f"Send GH₵{p.amount} to {p.recipient_name or 'recipient'}",
                    p.blocking_reason or "This transaction cannot be completed.",
                ]
            return "Confirm Transaction", body

        if self.state == ScreenState.RESULT:
            body = [self.last_result_message or ""]
            return "Result", body

        if self.state == ScreenState.HISTORY:
            history = self.world.transaction_history(self.sender_wallet_id)
            if not history:
                body = ["No transactions yet."]
            else:
                body = [
                    f"{tx.id}  GH₵{tx.amount}  {query_visible_status(tx).value.upper()}"
                    f"{'  (sent)' if tx.sender_wallet_id == self.sender_wallet_id else '  (received)'}"
                    for tx in history
                ]
            return "Transaction History", body

        if self.state == ScreenState.STATUS:
            tx_id = self.status_query_tx_id
            try:
                tx = self.world.transaction_status(tx_id) if tx_id else None
            except Exception:  # noqa: BLE001 - unknown tx id is expected input, not a bug
                tx = None
            if tx is None:
                body = ["Transaction not found."]
            else:
                body = [f"{tx.id}: {query_visible_status(tx).value.upper()}"]
            return "Transaction Status", body

        if self.state == ScreenState.BALANCE:
            balance = self.world.get_balance(self.sender_wallet_id)
            return "Balance", [f"GH₵{balance}"]

        if self.state == ScreenState.UNSUPPORTED:
            return "Not Available", ["This service is not available in this benchmark."]

        if self.state == ScreenState.TERMINAL:
            return "Session ended.", []

        return "", []
