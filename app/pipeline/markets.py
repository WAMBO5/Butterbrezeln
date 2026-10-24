"""Market layer of a run (design spec section 9.3). Reads the main result; never changes it."""

from __future__ import annotations

from typing import Any


async def run_markets_step(rc: Any) -> None:
    rc.state.markets_result = None
