"""`match_reviewer`: are the matcher's decisions sound? (design spec section 6.9)"""

from __future__ import annotations

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.agents.requirement_matcher import match_context
from app.config.settings import Settings
from app.matching.match import MatchInput
from app.models import GroupMatchBatch, Review

INSTRUCTION = """\
You review which candidate obligations a matcher selected as requirements for some parts of a
product, one regulation section at a time. You see every candidate and the selection. An obligation
belongs in the selection when its subject is one of the parts' device types or functions (or the
installation of that function) and it can apply to the product as described, including its
conditional obligations and the limits or pass/fail results it must reach in a test.

Flag only clear errors, one issue per obligation:
- "wrong_device": selected, but about another device type or function, or a part it does not bind.
- "absent_feature": selected, but it needs a feature the inputs show is absent, an optional add-on the
  inputs do not mention, or a vehicle category the product is not for.
- "test_method": selected, but it instructs the test laboratory (apparatus, conditioning, steps, how
  to compute results) instead of stating what the product must reach.
- "administrative": selected, but it concerns the authority, the application, approval numbering,
  communication or conformity of production.
- "missed": not selected, although it clearly binds a part as described; proposed "add".
target_id is the obligation id; reason says why; evidence lists fact or provision ids; proposed is
"remove" (or "add" for missed). Return verdict "pass" with no issues when the selection holds.
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
