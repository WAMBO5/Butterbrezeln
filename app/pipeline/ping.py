"""`certivity doctor --ping`: one minimal paid call per tier, with and without a tool, to prove
structured output works on the configured models (design spec section 17, risk 1)."""

from __future__ import annotations

import time

from app.agents.factory import ConfigError, make_agent
from app.config.settings import Settings
from app.llm import LLM, AgentOutputError, Budget, load_prices
from app.models import Review
from app.tools.corpus_tools import read_provision

PING_INSTRUCTION = "You answer connectivity checks. Follow the request exactly."


async def ping(settings: Settings, provision_id: str) -> list[dict]:
    llm = LLM(settings, budget=Budget(0.5, load_prices(settings.prices_path)))
    checks = [(tier, None) for tier in ("judgment", "fast", "review")] + [("judgment", "read_provision")]
    results = []
    for tier, tool in checks:
        row: dict = {"tier": tier, "tool": tool or "-"}
        try:
            spec = make_agent(name=f"ping_{tier}{'_tool' if tool else ''}", description="connectivity check",
                              instruction=PING_INSTRUCTION, output_schema=Review, tier=tier, effort="low",
                              settings=settings, tools=[read_provision] if tool else None, tool_call_limit=2,
                              max_tokens=2000)
            row["model"] = spec.model
            prompt = ("Call read_provision once with provision_id " + repr(provision_id) + ", then " if tool else "") \
                + 'Return verdict "pass" and an empty issues list.'
            started = time.monotonic()
            result = await llm.call(spec, prompt)
            row.update(ok=result.output.verdict == "pass", latency_s=round(time.monotonic() - started, 2),
                       tokens=result.usage.as_dict(), tool_calls=result.tool_calls, cost_usd=round(result.cost_usd, 5))
        except (ConfigError, AgentOutputError) as exc:
            row.update(ok=False, error=str(exc))
        results.append(row)
    return results
