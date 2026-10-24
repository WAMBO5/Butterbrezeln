"""`requirement_matcher`: which candidate obligations bind this part? (design spec section 6.5)"""

from __future__ import annotations

import json

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.matching.match import MatchInput
from app.models import GroupMatchBatch, Issue
from app.tools.corpus_tools import read_provision

INSTRUCTION = """\
You decide which candidate obligations of one regulation section bind which parts of a product. You
see the parts the scope plan assigned this section to; return exactly one decision per obligation id,
ids copied exactly:
- state "applicable" with part_ids: the parts the obligation binds as built or installed. This
  includes the section's general requirements that bind every device the regulation covers,
  installation rules for a part's function, markings, and the test procedures used to verify a part.
- state "not_applicable" with part_ids []: it binds none of these parts, because it is about another
  device type or function (a front position lamp rule for a rear lamp), a feature the inputs show the
  parts do not have (filament light sources when the light source is LED modules), or it is not an
  engineering requirement on the product at all: obligations on the approval authority, the
  application documents, approval numbering or the communication of approvals.
- state "uncertain" with part_ids: it may bind those parts but depends on a fact the inputs do not
  give. The spec being silent is never enough for not_applicable.
- reason: one sentence naming the fact or the device type it turns on.
- fact_refs: ids of the parts' facts you relied on.
- evidence_status: "met" when a fact shows it is fulfilled, "not_met" when a fact contradicts it
  (cite that fact), otherwise "evidence_needed".
- test_case: one line on how to verify it (test, measurement or document check).
Use read_provision only to look up a referenced annex or definition (at most 3 calls). If the payload
lists feedback, answer every issue.
"""


def create_requirement_matcher(settings: Settings) -> AgentSpec:
    effort = "low" if settings.cost_mode == "reduced" else "medium"
    return make_agent(name="requirement_matcher", description="Decides which obligations apply to a part",
                      instruction=INSTRUCTION, output_schema=GroupMatchBatch, tier="judgment", effort=effort,
                      settings=settings, tools=None if settings.cost_mode == "reduced" else [read_provision],
                      tool_call_limit=3)


def match_context(batch: MatchInput) -> list[tuple[str, str]]:
    card = batch.card
    obligations = "\n".join(
        f"[{o.obligation_id}] (paragraph {o.provision_id.split('#', 1)[1]}) {o.text}"
        + (f" — condition: {o.condition}" if o.condition else "") for o in batch.obligations)
    definitions = "\n".join(f"[{d.provision_id}] {' '.join(d.text.split())[:600]}" for d in batch.definitions)
    return [
        ("Parts assigned to this section", json.dumps([p.model_dump() for p in batch.parts], indent=1,
                                                       ensure_ascii=False)),
        ("Product summary", json.dumps(batch.product_summary, ensure_ascii=False)),
        ("Regulation card", json.dumps({"regulation": card.regulation, "title": card.title,
                                        "type": card.regulation_type, "devices_in_scope": card.devices_in_scope,
                                        "functions_covered": card.functions_covered, "triggers": card.triggers},
                                       ensure_ascii=False)),
        ("Section", " > ".join(batch.heading_path)),
        ("Candidate obligations", obligations),
        ("Referenced definitions", definitions or "(none)"),
    ]


def build_match_prompt(batch: MatchInput, feedback: list[Issue]) -> str:
    return render_prompt(
        task=f"Decide every candidate obligation for the parts {', '.join(batch.part_ids)}.",
        context=match_context(batch), untrusted=[],
        payload={"part_ids": batch.part_ids, "obligation_ids": [o.obligation_id for o in batch.obligations],
                 "feedback": [i.model_dump() for i in feedback]},
    )
