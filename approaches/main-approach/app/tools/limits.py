"""Per-call tool budgets: after `max_calls`, a tool answers with an error instead of running."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

EXHAUSTED = {"status": "error", "message": "Tool budget exhausted; answer with what you have."}


class ToolCallLimiter:
    def __init__(self, agent_name: str, max_calls: int):
        self.agent_name = agent_name
        self.max_calls = max_calls
        self.calls = 0

    def check(self) -> dict | None:
        """None while calls are left, the exhausted-error dict after that."""
        self.calls += 1
        return dict(EXHAUSTED) if self.calls > self.max_calls else None

    def wrap(self, fn: Callable[..., dict]) -> Callable[..., dict]:
        """`fn` with the same signature and docstring, counted against this budget."""

        @functools.wraps(fn)
        def limited(*args: Any, **kwargs: Any) -> dict:
            blocked = self.check()
            return blocked if blocked is not None else fn(*args, **kwargs)

        return limited
