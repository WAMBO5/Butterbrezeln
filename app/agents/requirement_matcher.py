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
You select, from the candidate obligations of one regulation section, the ones that a homologation
engineer would list as requirements for these parts of this product. Precision matters: list an
obligation only when it binds the parts as the inputs describe them. Obligations you do not list bind
none of the parts; there is no need to explain them.

Select an obligation only when all of these hold:
- It is about the device type or function of the parts (a rear position lamp rule for the rear
  position lamp, not for the stop lamp; a front lamp rule for none of them).
- It applies to the product as described. Leave out obligations that only apply to a variant or
  optional feature the inputs do not show: variable luminous intensity, sequential activation,
  manufacturer logos, interdependent lamp systems, movable components, replaceable light sources,
  categories or classes the spec does not name, fail-safe or replacement functions, other vehicle
  categories.
- It is a requirement on the product: a design, performance, photometric, colour, marking or
  installation requirement, or the pass/fail result a test must reach ("after the test the device
  shall show no cracking", "the intensity shall be at least 4 cd"). Leave out instructions to the
  test laboratory (apparatus, conditioning, test steps, how to measure or add up results), duties of
  the approval authority, the application documents, approval numbering, communication forms and
  conformity of production.

For each selected obligation: part_ids (the parts it binds), confidence "high" when you are sure it
binds those parts as described, "medium" when it most likely does but depends on a detail the inputs
leave open; reason (one sentence naming the device or fact it turns on); fact_refs (ids of the
parts' facts you used); evidence_status ("met" when a fact shows it is fulfilled, "not_met" when a
fact contradicts it, otherwise "evidence_needed"); test_case (one line on how to verify it). Copy
obligation ids exactly. Use read_provision only to look up a referenced annex or definition (at most 3
calls). If the payload lists feedback, answer every issue.
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
        task=f"Select the candidate obligations that bind the parts {', '.join(batch.part_ids)}.",
        context=match_context(batch), untrusted=[],
        payload={"part_ids": batch.part_ids, "obligation_ids": [o.obligation_id for o in batch.obligations],
                 "feedback": [i.model_dump() for i in feedback]},
    )
