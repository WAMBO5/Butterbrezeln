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
  installation rules for a part's function, markings, and the limits, pass/fail criteria, test
  levels and exposure conditions a part is verified against.
- state "not_applicable" with part_ids []: it binds none of these parts, because it is about another
  device type or function (a front position lamp rule for a rear lamp), a feature the inputs show the
  parts do not have (filament light sources when the light source is LED modules), or it is not an
  engineering requirement on the product at all: obligations on the approval authority, the
  application documents, approval numbering, the communication of approvals, the sampling plans
  and statistics of conformity-of-production checks; the mechanics of how a laboratory carries out a
  test (preparing, mounting, positioning or rotating the sample, masking, instrument set-up,
  calibration, recording, calculation steps); an alternative test method or test procedure, or a
  test that applies only at the manufacturer's request, together with its steps; and entries that
  only say whether the vehicle must carry the device ("Presence: mandatory" or "optional"). The
  conditions a requirement is defined or tested under stay applicable (test voltage, the field or
  directions where a value is measured, illuminant, frequency range, modulation, test solution,
  exposure standard), and so do alternative designs or installation options of the part.
- device categories and classes: where the regulation sets requirements per category or class of a
  device, an obligation for a category or class the part cannot belong to, given its type, position
  and function in the product, is not_applicable; use uncertain only when the part could belong to it.
- state "uncertain" with part_ids: it is about the part's own device type or function but depends on
  a fact the inputs do not give: a feature the inputs neither show nor exclude (a logo, replaceable
  light source modules, a particular mounting position), or a rule for optional or additional
  devices of the part's own function ("where optional lamps are installed", "if fitted"). The spec
  being silent is never enough for not_applicable; an obligation for a device type or function the
  part does not have is not_applicable, not uncertain.
- reason: one sentence naming the fact or the device type it turns on.
- fact_refs: ids of the parts' facts you relied on.
- evidence_status: "met" when a fact shows it is fulfilled, "not_met" when a fact contradicts it
  (cite that fact), otherwise "evidence_needed".
- test_case: one line on how to verify it (test, measurement or document check).
Use read_provision only to look up a referenced annex or definition (at most 3 calls). If the payload
lists feedback, answer every issue.
"""


def create_requirement_matcher(settings: Settings) -> AgentSpec:
    effort = "medium"  # low effort did not follow the not_applicable rules reliably (dev runs 1–2)
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
