import pytest

from app.agents.factory import ConfigError, make_agent, model_id_for
from app.config.settings import load_settings
from app.llm import LLM, AgentOutputError, build_request
from app.models import Review
from app.testing.fake_llm import register_responders

SETTINGS = load_settings({"ANTHROPIC_MODEL": "judge-model", "ANTHROPIC_MODEL_FAST": "fast-model"})


def _spec(**kw):
    args = dict(name="probe_agent", description="d", instruction="i", output_schema=Review, tier="fast",
                effort="low", settings=SETTINGS)
    args.update(kw)
    return make_agent(**args)


def test_request_follows_current_model_rules():
    req = build_request(_spec(), "hello")
    assert req["model"] == "fast-model" and req["output_config"] == {"effort": "low"}
    assert not {"thinking", "temperature", "top_p", "top_k", "tool_choice"} & set(req)
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert req["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]


def test_review_tier_falls_back_to_judgment():
    assert _spec(tier="review").model == "judge-model"


def test_missing_fast_model_is_a_config_error():
    with pytest.raises(ConfigError, match="ANTHROPIC_MODEL_FAST"):
        model_id_for("fast", load_settings({"ANTHROPIC_MODEL": "m"}))


def test_fake_model_ids():
    spec = _spec(settings=load_settings({}, fake_llm=True))
    assert spec.model == "fake/probe_agent"


async def test_fake_invalid_output_raises_agent_output_error():
    fake = load_settings({}, fake_llm=True)
    register_responders({"bad_agent": lambda prompt, req: "not json"})
    spec = make_agent(name="bad_agent", description="d", instruction="i", output_schema=Review, tier="fast",
                      effort="low", settings=fake)
    with pytest.raises(AgentOutputError) as err:
        await LLM(fake).call(spec, "x")
    assert err.value.agent_name == "bad_agent"


async def test_fake_missing_responder_returns_empty_object():
    fake = load_settings({}, fake_llm=True)
    spec = make_agent(name="nobody_agent", description="d", instruction="i", output_schema=Review, tier="fast",
                      effort="low", settings=fake)
    with pytest.raises(AgentOutputError):  # "{}" does not validate as a Review
        await LLM(fake).call(spec, "x")


def test_tools_are_wrapped_with_limit(mini_store):
    from app.llm import build_tools
    from app.tools import corpus_tools as ct

    ct.bind_store(mini_store)
    spec = _spec(tools=[ct.read_provision], tool_call_limit=1)
    tools, limiter = build_tools(spec)
    assert [t.name for t in tools] == ["read_provision"] and limiter.max_calls == 1
