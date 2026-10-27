"""The only module that talks to the Anthropic API (ENGINEERING.md ground rule 1).

`LLM.call(spec, prompt)` runs any `AgentSpec`: one structured call (`messages.parse`), or a bounded
tool loop (`beta.messages.tool_runner`) when the spec has tools. It counts tokens and cost per
agent, enforces the run budget, tells listeners (trace, UI) what happened, and swaps in the
scripted fake model when `settings.fake_llm` is set.
"""

from __future__ import annotations

import functools
import json
import logging
import threading
import time
from pathlib import Path
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ValidationError

from app.agents.factory import AgentSpec
from app.agents.prompting import prompt_text
from app.config.settings import Settings
from app.testing.fake_llm import fake_respond
from app.tools.limits import ToolCallLimiter

log = logging.getLogger(__name__)

Prompt = str | list[dict]
Listener = Callable[[dict], None]
FAKE_USAGE = (1000, 200)


class AgentOutputError(Exception):
    """A model call that produced no usable output (API error, refusal, truncation, invalid schema)."""

    def __init__(self, agent_name: str, message: str):
        super().__init__(f"{agent_name}: {message}")
        self.agent_name = agent_name
        self.message = message


class BudgetExceeded(AgentOutputError):
    """The run budget is spent; no further model calls are made."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def add(self, usage: Any) -> None:
        if usage is None:
            return
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def as_dict(self) -> dict[str, int]:
        return {"input": self.input_tokens, "output": self.output_tokens, "cache_read": self.cache_read,
                "cache_write": self.cache_write}


class BudgetLike(Protocol):
    def check(self, agent_name: str) -> None: ...

    def charge(self, agent_name: str, model: str, usage: Usage) -> float: ...


@dataclass(frozen=True)
class ModelPrice:
    input: float
    output: float
    cache_read: float | None


def load_prices(path: Path) -> dict[str, ModelPrice]:
    """USD per million tokens per model id, from `app/config/prices.yaml` (no prices in code)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {model: ModelPrice(input=float(v["input"]), output=float(v["output"]),
                              cache_read=None if v.get("cache_read") is None else float(v["cache_read"]))
            for model, v in data.items()}


def cost_usd(price: ModelPrice, prompt_tokens: int, cached_tokens: int, output_tokens: int,
             cache_write_tokens: int = 0) -> float:
    """Prompt tokens include cached and cache-written tokens; cache writes cost 1.25 x input."""
    fresh = prompt_tokens - cached_tokens - cache_write_tokens
    read = price.cache_read if price.cache_read is not None else price.input
    return (fresh * price.input + cached_tokens * read + cache_write_tokens * price.input * 1.25
            + output_tokens * price.output) / 1e6


class Budget:
    """Tokens and cost per agent for one run; blocks further calls once `max_cost_usd` is spent."""

    def __init__(self, max_cost_usd: float, prices: dict[str, ModelPrice]):
        self.max_cost_usd = max_cost_usd
        self.prices = prices
        self.spent_usd = 0.0
        self.per_agent: dict[str, dict] = {}
        self._warned: set[str] = set()
        self._lock = threading.Lock()

    @property
    def exceeded(self) -> bool:
        return self.spent_usd >= self.max_cost_usd

    def _price(self, model: str) -> ModelPrice | None:
        if model in self.prices:
            return self.prices[model]
        if model.startswith("fake/") and "fake" in self.prices:
            return self.prices["fake"]
        if model not in self._warned:
            self._warned.add(model)
            log.warning("no price for model %s; its cost is counted as 0", model)
        return None

    def check(self, agent_name: str) -> None:
        if self.exceeded:
            raise BudgetExceeded(agent_name, f"run budget of ${self.max_cost_usd:.2f} reached")

    def charge(self, agent_name: str, model: str, usage: Usage) -> float:
        price = self._price(model)
        prompt = usage.input_tokens + usage.cache_read + usage.cache_write
        cost = cost_usd(price, prompt, usage.cache_read, usage.output_tokens, usage.cache_write) if price else 0.0
        with self._lock:
            self.spent_usd += cost
            row = self.per_agent.setdefault(agent_name, {"model": model, "calls": 0, "input": 0, "output": 0,
                                                         "cache_read": 0, "cache_write": 0, "cost_usd": 0.0})
            row["calls"] += 1
            for key, value in usage.as_dict().items():
                row[key] += value
            row["cost_usd"] = round(row["cost_usd"] + cost, 6)
        return cost

    def report(self) -> dict:
        return {"max_cost_usd": self.max_cost_usd, "spent_usd": round(self.spent_usd, 6), "exceeded": self.exceeded,
                "per_agent": self.per_agent}


@dataclass
class AgentResult:
    output: BaseModel
    model: str
    usage: Usage
    cost_usd: float
    request_id: str | None
    latency_s: float
    tool_calls: int = 0


def _content(prompt: Prompt) -> list[dict]:
    return [{"type": "text", "text": prompt}] if isinstance(prompt, str) else list(prompt)


def build_request(spec: AgentSpec, prompt: Prompt) -> dict:
    """The Messages API request for one agent call: cached system prompt, one user turn, effort.

    No `thinking` (adaptive by default), no sampling parameters, no forced `tool_choice`
    (ENGINEERING.md ground rule 4)."""
    return {
        "model": spec.model,
        "max_tokens": spec.max_tokens,
        "system": [{"type": "text", "text": spec.instruction, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": _content(prompt)}],
        "output_config": {"effort": spec.effort},
    }


def build_tools(spec: AgentSpec) -> tuple[list[Any], ToolCallLimiter]:
    """The spec's plain tool functions as SDK tools, JSON-encoded and counted against its limit."""
    from anthropic import beta_async_tool

    limiter = ToolCallLimiter(spec.name, spec.tool_call_limit or 10)
    tools = []
    for fn in spec.tools:
        limited = limiter.wrap(fn)

        @functools.wraps(fn)
        async def as_text(*args: Any, _fn: Callable[..., dict] = limited, **kwargs: Any) -> str:
            return json.dumps(_fn(*args, **kwargs), ensure_ascii=False)

        as_text.__annotations__ = {**fn.__annotations__, "return": str}
        tools.append(beta_async_tool(as_text, name=fn.__name__))
    return tools, limiter


@dataclass
class LLM:
    settings: Settings
    budget: BudgetLike | None = None
    listeners: list[Listener] = field(default_factory=list)
    _client: Any = None

    def _api(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(max_retries=4, timeout=900.0)
        return self._client

    def _emit(self, event: dict) -> None:
        for listener in self.listeners:
            try:
                listener(event)
            except Exception:  # a broken listener must not break a run
                log.exception("trace listener failed")

    async def run_agent(self, spec: AgentSpec, prompt: Prompt) -> BaseModel:
        return (await self.call(spec, prompt)).output

    async def call(self, spec: AgentSpec, prompt: Prompt) -> AgentResult:
        if self.budget is not None:
            try:
                self.budget.check(spec.name)
            except BudgetExceeded as exc:
                self._emit({"event": "agent_blocked", "agent": spec.name, "error": exc.message})
                raise
        self._emit({"event": "agent_start", "agent": spec.name, "model": spec.model})
        started = time.monotonic()
        try:
            if self.settings.fake_llm:
                result = self._fake(spec, prompt)
            else:
                result = await self._real(spec, prompt)
        except AgentOutputError as exc:
            self._emit({"event": "agent_error", "agent": spec.name, "model": spec.model, "error": exc.message})
            raise
        result.latency_s = round(time.monotonic() - started, 3)
        self._emit({"event": "agent_end", "agent": spec.name, "model": spec.model, "usage": result.usage.as_dict(),
                    "cost_usd": result.cost_usd, "latency_s": result.latency_s, "tool_calls": result.tool_calls})
        return result

    def _charge(self, spec: AgentSpec, usage: Usage) -> float:
        return self.budget.charge(spec.name, spec.model, usage) if self.budget is not None else 0.0

    def _fake(self, spec: AgentSpec, prompt: Prompt) -> AgentResult:
        content = _content(prompt)
        text = fake_respond(spec.name, spec.instruction, prompt_text(prompt),
                            sum(1 for b in content if b.get("type") == "image"), n_contents=1)
        usage = Usage(input_tokens=FAKE_USAGE[0], output_tokens=FAKE_USAGE[1])
        cost = self._charge(spec, usage)
        try:
            output = spec.output_model.model_validate_json(text)
        except ValidationError as exc:
            raise AgentOutputError(spec.name, f"output does not match {spec.output_model.__name__}: {exc}") from exc
        return AgentResult(output=output, model=spec.model, usage=usage, cost_usd=cost, request_id=None, latency_s=0.0)

    async def _real(self, spec: AgentSpec, prompt: Prompt) -> AgentResult:
        import anthropic

        request = build_request(spec, prompt)
        usage = Usage()
        tool_calls = 0
        try:
            if spec.tools:
                tools, limiter = build_tools(spec)
                runner = self._api().beta.messages.tool_runner(
                    **request, tools=tools, output_format=spec.output_model,
                    max_iterations=(spec.tool_call_limit or 10) + 3,
                )
                message = None
                async for message in runner:
                    usage.add(message.usage)
                    if self.budget is not None:
                        try:
                            self.budget.check(spec.name)
                        except BudgetExceeded:
                            self._charge(spec, usage)
                            await runner.close()
                            raise
                tool_calls = limiter.calls
            else:
                message = await self._api().messages.parse(**request, output_format=spec.output_model)
                usage.add(message.usage)
        except anthropic.APIStatusError as exc:
            self._charge(spec, usage)
            raise AgentOutputError(spec.name, f"API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            self._charge(spec, usage)
            raise AgentOutputError(spec.name, f"connection error: {exc}") from exc
        except (ValidationError, ValueError) as exc:
            self._charge(spec, usage)
            raise AgentOutputError(spec.name, f"output could not be parsed: {exc}") from exc
        cost = self._charge(spec, usage)
        if message is None:
            raise AgentOutputError(spec.name, "no response")
        if message.stop_reason == "refusal":
            raise AgentOutputError(spec.name, "the model declined the request (refusal)")
        if message.stop_reason == "max_tokens":
            raise AgentOutputError(spec.name, f"output truncated at max_tokens={spec.max_tokens}")
        parsed = getattr(message, "parsed_output", None)
        if parsed is None:
            raise AgentOutputError(spec.name, f"no structured output (stop_reason={message.stop_reason})")
        return AgentResult(output=parsed, model=spec.model, usage=usage, cost_usd=cost,
                           request_id=getattr(message, "_request_id", None), latency_s=0.0, tool_calls=tool_calls)
