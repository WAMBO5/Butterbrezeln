"""Agent calls as the pipeline sees them: run through `LLM`, recorded in the run's ledger."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from app.agents.factory import AgentSpec
from app.agents.prompting import prompt_text
from app.compliance.ledger import Ledger
from app.llm import LLM, AgentOutputError, Prompt

AgentCall = Callable[[AgentSpec, Prompt], Awaitable[BaseModel]]


def ledger_input(prompt: Prompt) -> dict:
    """The prompt as recorded: the text in full, images as hashes."""
    if isinstance(prompt, str):
        return {"prompt": prompt}
    images = [hashlib.sha256(b["source"]["data"].encode("ascii")).hexdigest()
              for b in prompt if b.get("type") == "image"]
    return {"prompt": prompt_text(prompt), "images_sha256": images}


async def call_agent(llm: LLM, spec: AgentSpec, prompt: Prompt, ledger: Ledger | None) -> BaseModel:
    """Run one isolated agent call and append an `agent_call` record; errors are recorded, then raised."""
    meta: dict[str, Any] = {"model": spec.model, "effort": spec.effort, "tier": spec.tier,
                            "prompt_version": spec.prompt_version}
    try:
        result = await llm.call(spec, prompt)
    except AgentOutputError as exc:
        if ledger is not None:
            ledger.append("agent_call", spec.name, ledger_input(prompt), None, {**meta, "error": exc.message})
        raise
    if ledger is not None:
        ledger.append("agent_call", spec.name, ledger_input(prompt), result.output, {
            **meta, "tokens": result.usage.as_dict(), "cost_usd": round(result.cost_usd, 6),
            "request_id": result.request_id, "latency_s": result.latency_s, "tool_calls": result.tool_calls,
        })
    return result.output


def bind_call(llm: LLM, ledger: Ledger | None) -> AgentCall:
    async def call(spec: AgentSpec, prompt: Prompt) -> BaseModel:
        return await call_agent(llm, spec, prompt, ledger)

    return call


async def gather_limited(coros: list, limit: int) -> list:
    """Run coroutines with at most `limit` at a time; results in input order (AGENTS.md fan-out)."""
    semaphore = asyncio.Semaphore(max(1, limit))

    async def one(coro: Any) -> Any:
        async with semaphore:
            return await coro

    return await asyncio.gather(*(one(c) for c in coros))
