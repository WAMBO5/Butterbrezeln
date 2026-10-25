"""`match_reviewer`: are the matcher's decisions sound? (design spec section 6.9)"""

from __future__ import annotations

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.agents.requirement_matcher import match_context
from app.config.settings import Settings
from app.matching.match import MatchInput
from app.models import GroupMatchBatch, Review

INSTRUCTION = """\
You review a matcher's decisions on which obligations of one regulation section bind which parts of
a product. You see the matcher's full context and its decisions. Regulations prescribe outcomes, and a
specification describes construction, so an obligation binds a part through the part's function,
behaviour, role or installation; the specification's silence about an outcome is never a reason to
exclude it. The matcher may exclude an obligation only as other_function, other_class,
other_vehicle, shown_absent, presence_only or alternative_method. Flag only real errors:
- "silent_spec": not_applicable that rests only on the specification not mentioning the outcome or
  the feature; proposed "uncertain" or "applicable".
- "wrong_function": applicable or uncertain for an obligation about another device type, function,
  class or vehicle category, or for a part it does not bind; proposed "not_applicable" with the
  exclusion that holds.
- "bad_exclusion": not_applicable with an exclusion that does not hold for these parts (another
  function that the part in fact performs, a class it could be, a feature the inputs do not show
  absent); proposed "applicable" or "uncertain".
- "unbacked_evidence": evidence_status met or not_met that no cited fact supports; proposed
  "evidence_needed".
Each issue: target_id the obligation id, reason, evidence (fact or provision ids), proposed the
corrected value. Return verdict "pass" with no issues when the decisions are sound.
"""


def create_match_reviewer(settings: Settings) -> AgentSpec:
    return make_agent(name="match_reviewer", description="Reviews the matcher's decisions",
                      instruction=INSTRUCTION, output_schema=Review, tier="match", effort="high", settings=settings)


def build_match_review_prompt(batch: MatchInput, out: GroupMatchBatch) -> str:
    decisions = "\n".join(f"[{d.obligation_id}] {d.state}{f' ({d.exclusion})' if d.exclusion else ''} "
                          f"parts={d.part_ids} / {d.evidence_status} facts={d.fact_refs} — {d.reason}"
                          for d in out.decisions)
    return render_prompt(task=f"Review the decisions for the parts {', '.join(batch.part_ids)}.",
                         context=[*match_context(batch), ("Matcher decisions", decisions)], untrusted=[],
                         payload={"part_ids": batch.part_ids})
