"""`match_reviewer`: are the matcher's decisions sound? (design spec section 6.9)"""

from __future__ import annotations

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.agents.requirement_matcher import match_context
from app.config.settings import Settings
from app.matching.match import MatchInput
from app.models import GroupMatchBatch, Review

INSTRUCTION = """\
You review the obligations a matcher selected as requirements for some parts of a product, one
regulation section at a time. Your job is precision: challenge every selection that a homologation
engineer would not list for these parts. Flag, one issue per obligation:
- "wrong_device": it is about another device type or function, or a part it does not bind.
- "conditional": it only applies to a variant or optional feature the inputs do not show (variable
  intensity, logos, movable components, other categories or classes, fail-safe functions).
- "test_method": it is an instruction to the test laboratory (apparatus, conditioning, steps,
  measurement method), not the result the product must reach.
- "administrative": it concerns the authority, the application, approval numbering, communication or
  conformity of production.
- "missed": a candidate the matcher left out that clearly binds a part as described (only when you
  are certain); proposed "add".
target_id is the obligation id; reason says why; evidence lists fact or provision ids; proposed is
"remove" (or "add" for missed). Return verdict "pass" with no issues when every selection holds.
"""


def create_match_reviewer(settings: Settings) -> AgentSpec:
    return make_agent(name="match_reviewer", description="Reviews the matcher's decisions",
                      instruction=INSTRUCTION, output_schema=Review, tier="review", effort="high", settings=settings)


def build_match_review_prompt(batch: MatchInput, out: GroupMatchBatch) -> str:
    decisions = "\n".join(f"[{d.obligation_id}] selected for {d.part_ids} ({d.confidence}) / {d.evidence_status} "
                          f"facts={d.fact_refs} — {d.reason}" for d in out.decisions) or "(nothing selected)"
    return render_prompt(task=f"Review the obligations selected for the parts {', '.join(batch.part_ids)}.",
                         context=[*match_context(batch), ("Matcher decisions", decisions)], untrusted=[],
                         payload={"part_ids": batch.part_ids})
