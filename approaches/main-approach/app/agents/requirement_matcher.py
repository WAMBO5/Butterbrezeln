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
You select, from the candidate obligations of one regulation section, the ones that bind these parts
of the product, as a homologation engineer would list them. Obligations you do not list bind none of
the parts; there is no need to explain them.

Select an obligation when its subject is one of the parts' device types or functions, or the
installation of that function on a vehicle, and it can apply to the product as described:
- requirements on design, performance, emitted or reflected light, colour, materials, markings and
  durability, including the limits or pass/fail results the part must reach in a test, also when
  the text says how they are measured;
- installation rules for the parts' functions: position, number, spacing, visibility, orientation,
  electrical connections and tell-tales;
- conditional obligations whose condition concerns the part itself or how it is built, combined or
  installed ("where the lamp is mounted below ...", "if the device is combined with ..."). The
  condition is part of the requirement; select it.

Leave an obligation out when:
- it is about another device type or function than the parts' (a rule for a different kind of
  device, or for a different light function);
- it needs a feature the inputs show the product does not have, or an optional add-on the inputs do
  not mention (for example a variable or adaptive control function, a decorative logo, sequential
  activation, a fail-safe replacement function), or it is limited to vehicle categories the product
  is not for;
- it instructs the test laboratory rather than the product: test apparatus, conditioning, the order
  of test steps, how to compute or record results;
- it concerns the approval procedure: the authority, application documents, approval numbering,
  communication forms, conformity of production.

For each selected obligation: part_ids (the parts it binds), confidence "high" when it clearly binds
those parts as described, "medium" when it binds them only if a detail the inputs leave open turns
out a certain way; reason (one sentence naming the device or fact it turns on); fact_refs (ids of the
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
