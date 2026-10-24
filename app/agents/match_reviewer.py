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
a product. You see the matcher's full context and its decisions. Flag only real errors:
- "silent_spec": not_applicable that rests only on the spec being silent; proposed "uncertain".
- "wrong_device": applicable for an obligation about another device type or function, or for a part
  it does not bind; proposed "not_applicable".
- "missed": not_applicable, or a part left out, for an obligation that does bind it; proposed
  "applicable".
- "unbacked_evidence": evidence_status met or not_met that no cited fact supports; proposed
  "evidence_needed".
Each issue: target_id the obligation id, reason, evidence (fact or provision ids), proposed the
corrected value. Return verdict "pass" with no issues when the decisions are sound.
"""


def create_match_reviewer(settings: Settings) -> AgentSpec:
    return make_agent(name="match_reviewer", description="Reviews the matcher's decisions",
                      instruction=INSTRUCTION, output_schema=Review, tier="review", effort="high", settings=settings)


def build_match_review_prompt(batch: MatchInput, out: GroupMatchBatch) -> str:
    decisions = "\n".join(f"[{d.obligation_id}] {d.state} parts={d.part_ids} / {d.evidence_status} "
                          f"facts={d.fact_refs} — {d.reason}" for d in out.decisions)
    return render_prompt(task=f"Review the decisions for the parts {', '.join(batch.part_ids)}.",
                         context=[*match_context(batch), ("Matcher decisions", decisions)], untrusted=[],
                         payload={"part_ids": batch.part_ids})
