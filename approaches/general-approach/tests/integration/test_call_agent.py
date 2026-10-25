import pytest

from app.agents.factory import make_agent
from app.compliance.ledger import Ledger
from app.config.settings import load_settings
from app.llm import LLM
from app.models import Review
from app.pipeline.calls import bind_call
from app.testing.fake_llm import CALLS, register_responders

pytestmark = pytest.mark.integration


async def test_each_call_sees_only_its_prompt(tmp_path):
    fake_settings = load_settings({"ANTHROPIC_MODEL": "x", "ANTHROPIC_MODEL_FAST": "y"}, fake_llm=True)
    register_responders({"probe_agent": lambda prompt, req: '{"verdict": "pass", "issues": []}'})
    agent = make_agent(name="probe_agent", description="d", instruction="i", output_schema=Review,
                       tier="fast", effort="low", settings=fake_settings)
    led = Ledger(tmp_path)
    CALLS.pop("probe_agent", None)
    call = bind_call(LLM(fake_settings), led)
    a = await call(agent, "first")
    b = await call(agent, "second")
    assert [a.verdict, b.verdict] == ["pass", "pass"]
    assert [c.prompt for c in CALLS["probe_agent"]] == ["first", "second"]
    assert all(c.n_contents == 1 for c in CALLS["probe_agent"])
    records = led.records()
    assert [r.kind for r in records] == ["agent_call", "agent_call"]
    assert records[0].meta["model"] == "fake/probe_agent" and records[0].meta["prompt_version"]
