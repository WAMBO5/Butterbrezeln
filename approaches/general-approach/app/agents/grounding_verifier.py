"""`grounding_verifier`: is each claim supported by the text it cites? (design spec section 6.9)"""

from __future__ import annotations

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.models import Claim, Review

INSTRUCTION = """\
You check claims against the text they cite. For each claim, decide whether its cited text supports
it. Judge only support by the cited text; do not use outside knowledge, and do not rewrite claims.

Return verdict "pass" when every claim is supported. Otherwise return "retry" with one issue per claim
that is not supported or only partly supported: type "unsupported" or "partly_supported", target_id
the claim id, reason what the cited text does or does not say, evidence [], proposed null.
"""


def create_grounding_verifier(settings: Settings) -> AgentSpec:
    return make_agent(name="grounding_verifier", description="Checks claims against their cited text",
                      instruction=INSTRUCTION, output_schema=Review, tier="fast", effort="low", settings=settings)


def build_grounding_prompt(claims: list[Claim]) -> str:
    return render_prompt(task="Check whether each claim is supported by its cited text.", context=[],
                         untrusted=[], payload={"claims": [c.model_dump() for c in claims]})
