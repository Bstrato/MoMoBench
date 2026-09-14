"""A simulated integer clock. Benchmark logic must never depend on wall-clock
time — only on this deterministic step counter, so that the same scenario
seed always produces the same event schedule."""

from __future__ import annotations


class SimClock:
    def __init__(self, start: int = 0) -> None:
        self.t = start

    def tick(self, n: int = 1) -> int:
        self.t += n
        return self.t

    def now(self) -> int:
        return self.t
