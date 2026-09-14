"""Deterministic ID generation.

All IDs used for scoring/ledger purposes must be reproducible from a scenario
seed plus a monotonic counter — never from wall-clock time or `uuid4()`.
"""

from __future__ import annotations


class SequentialIdFactory:
    """Produces zero-padded sequential IDs with a fixed prefix, e.g. TX000001."""

    def __init__(self, prefix: str, width: int = 6, start: int = 1) -> None:
        self.prefix = prefix
        self.width = width
        self._next = start

    def next(self) -> str:
        value = f"{self.prefix}{self._next:0{self.width}d}"
        self._next += 1
        return value

    def peek_next(self) -> str:
        return f"{self.prefix}{self._next:0{self.width}d}"
