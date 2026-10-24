"""Offline sanity check that the ADK + LLM (LiteLLM) stack composes. No API calls."""
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import AgentTool


def test_supervisor_can_wrap_specialist_as_agent_tool():
    model = LiteLlm(model="anthropic/claude-sonnet-5-5")
    specialist = Agent(name="specialist", model=model, instruction="Answer briefly.")
    supervisor = Agent(
        name="supervisor",
        model=model,
        instruction="Delegate to the specialist.",
        tools=[AgentTool(agent=specialist)],
    )

    assert isinstance(supervisor.tools[0], AgentTool)
    assert supervisor.tools[0].agent is specialist
