import json

import pytest

from app.agents.factory import make_agent
from app.compliance.trace import Trace
from app.config.settings import load_settings
from app.llm import LLM, Budget, BudgetExceeded, ModelPrice, Usage, cost_usd, load_prices
from app.models import Review
from app.testing.fake_llm import CALLS, register_responders

PRICES = load_prices(load_settings({}).prices_path)


def test_prices_and_cost():
    sonnet = PRICES["claude-sonnet-5-5"]
    assert cost_usd(sonnet, 1_000_000, 0, 0) == pytest.approx(2.0)
    assert cost_usd(sonnet, 1_000_000, 500_000, 0) == pytest.approx(1.1)
    assert cost_usd(PRICES["claude-haiku-5-5"], 1_000_000, 1_000_000, 0) == pytest.approx(0.1)  # unknown cache price


def test_budget_charges_per_agent_and_blocks():
    budget = Budget(0.01, {"fake": ModelPrice(input=1.0, output=1.0, cache_read=None)})
    cost = budget.charge("a", "fake/a", Usage(input_tokens=5000, output_tokens=5000))
    assert cost == pytest.approx(0.01) and budget.exceeded and budget.per_agent["a"]["calls"] == 1
    with pytest.raises(BudgetExceeded):
        budget.check("b")
    assert budget.report()["spent_usd"] == pytest.approx(0.01)


def test_unknown_model_costs_nothing():
    budget = Budget(1.0, {})
    assert budget.charge("a", "mystery", Usage(input_tokens=10**6)) == 0.0


async def test_blocked_call_never_reaches_the_model():
    settings = load_settings({}, fake_llm=True)
    register_responders({"budget_probe": lambda p, r: '{"verdict":"pass","issues":[]}'})
    spec = make_agent(name="budget_probe", description="d", instruction="i", output_schema=Review, tier="fast",
                      effort="low", settings=settings)
    llm = LLM(settings, budget=Budget(1e-9, {"fake": ModelPrice(input=1, output=1, cache_read=None)}))
    CALLS.pop("budget_probe", None)
    await llm.call(spec, "one")
    with pytest.raises(BudgetExceeded):
        await llm.call(spec, "two")
    assert len(CALLS["budget_probe"]) == 1


def test_trace_lines_are_json_and_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-trace-555")
    seen = []
    trace = Trace(tmp_path / "trace.jsonl", [seen.append])
    trace({"event": "agent_start", "agent": "x", "note": "sk-trace-555", "api_key": "sk-trace-555"})
    trace({"event": "agent_end", "agent": "x"})
    lines = (tmp_path / "trace.jsonl").read_text().splitlines()
    assert [json.loads(l)["event"] for l in lines] == ["agent_start", "agent_end"] and len(seen) == 2
    assert "sk-trace-555" not in (tmp_path / "trace.jsonl").read_text() and "ts" in json.loads(lines[0])
