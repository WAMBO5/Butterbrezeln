"""`AgentSpec`: an agent is a definition, run by `app.llm.LLM` (ENGINEERING.md, Architecture)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from app.compliance.manifest import prompt_version
from app.config.settings import Settings

Tier = Literal["judgment", "fast", "review"]
Effort = Literal["low", "medium", "high"]

AGENT_MODEL_IDS: dict[str, str] = {}
INSTRUCTIONS: dict[str, str] = {}


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class AgentSpec:
    name: str
    description: str
    instruction: str
    output_model: type[BaseModel]
    tier: Tier
    effort: Effort
    model: str
    tools: tuple[Callable[..., dict], ...] = field(default_factory=tuple)
    tool_call_limit: int | None = None
    max_tokens: int = 16000

    @property
    def prompt_version(self) -> str:
        return prompt_version(self.instruction)


_TIER_VARS = {"judgment": "ANTHROPIC_MODEL", "fast": "ANTHROPIC_MODEL_FAST", "review": "ANTHROPIC_MODEL_REVIEW"}


def model_id_for(tier: Tier, settings: Settings) -> str:
    model = {"judgment": settings.model_judgment, "fast": settings.model_fast, "review": settings.model_review}[tier]
    if not model:
        raise ConfigError(f"{_TIER_VARS[tier]} is not set")
    return model


def make_agent(
    *,
    name: str,
    description: str,
    instruction: str,
    output_schema: type[BaseModel],
    tier: Tier,
    effort: Effort,
    settings: Settings,
    tools: list[Callable[..., dict]] | None = None,
    tool_call_limit: int | None = None,
    max_tokens: int = 16000,
) -> AgentSpec:
    model = f"fake/{name}" if settings.fake_llm else model_id_for(tier, settings)
    AGENT_MODEL_IDS[name] = model
    INSTRUCTIONS[name] = instruction
    return AgentSpec(
        name=name, description=description, instruction=instruction, output_model=output_schema, tier=tier,
        effort=effort, model=model, tools=tuple(tools or ()), tool_call_limit=tool_call_limit, max_tokens=max_tokens,
    )
