"""Fixed observation rendering (spec §29). Every observation follows the
same [TASK]/[OPERATOR]/[SCREEN]/[AVAILABLE ACTIONS]/[STEP] layout across all
three operators and both interface layers. Never includes scenario tags,
failure mode, hidden ledger truth, or evaluator fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AvailableAction:
    action: str
    value_hint: str | None = None

    def render(self) -> str:
        if self.value_hint is not None:
            return f'{{"action":"{self.action}","value":"{self.value_hint}"}}'
        return f'{{"action":"{self.action}"}}'


def render_observation(
    *,
    task: str,
    operator_display_name: str,
    screen_title: str,
    screen_body: list[str],
    actions: list[AvailableAction],
    step: int,
    max_steps: int,
    error: str | None = None,
) -> str:
    lines = ["[TASK]", task, "", "[OPERATOR]", operator_display_name, "", "[SCREEN]", screen_title]

    if screen_body:
        lines.append("")
        lines.extend(screen_body)

    if error:
        lines.append("")
        lines.append(error)

    lines.append("")
    lines.append("[AVAILABLE ACTIONS]")
    for a in actions:
        lines.append(a.render())

    lines.append("")
    lines.append("[STEP]")
    lines.append(f"{step} / {max_steps}")

    return "\n".join(lines)
