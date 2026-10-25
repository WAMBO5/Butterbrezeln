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
You decide which obligations of one regulation section bind which parts of a product.

UN Regulations prescribe outcomes: what a device or system must achieve, under which conditions,
plus some design rules and markings. A product specification describes construction: parts,
materials, layout. So an obligation binds a part because of what the part is and does: its function,
its role on the vehicle, what it emits, transmits, absorbs or touches, what it is exposed to, and where
it is installed. The specification is almost always silent about outcomes, and its silence is never a
reason to exclude. Every obligation below is a product outcome, outcome condition, design rule or
permission (its role is shown); text that only instructs a laboratory or the approval authority has
already been removed.

Return exactly one decision per obligation id, ids copied exactly:
- "applicable" with part_ids: it binds those parts through their function, behaviour, role or
  installation. This includes the general requirements for every device the regulation covers, the
  installation rules for a part's function, markings, the conditions under which an outcome is
  defined or measured, and design or installation options open to the part.
- "uncertain" with part_ids: it concerns a part's own function, but depends on a design choice, an
  optional feature or an installation detail the inputs neither show nor exclude, or it is a rule for
  optional or additional devices of the part's own function ("if fitted"). Uncertain obligations
  are reported for an engineer to confirm.
- "not_applicable" with part_ids [] and one exclusion:
  - "other_function": it is about another device type or function than the parts have. When a part
    only houses, frames or mounts a device that is not part of the product, that device's own
    outcomes are other_function for the part, except where they constrain the part itself (its
    position, openings, or obstruction of the device);
  - "other_class": it is for a class, category, colour or variant of the device that the parts cannot
    be, given their function, attributes and position; if they could be, use "uncertain";
  - "other_vehicle": its own text limits it to vehicle categories the inputs show the product is not
    for. Do not infer this from rules elsewhere about which vehicles may carry a device: a rule for
    optional or additional devices of the part's own function is "uncertain";
  - "shown_absent": it needs a feature the inputs show is absent; cite that fact in fact_refs;
  - "presence_only": it only says whether the vehicle must or may carry the device at all;
  - "alternative_method": it belongs to one of several test methods the regulation offers as
    alternatives, of which the laboratory or applicant chooses one (its specific set-up, field
    generation or equipment); limits and conditions that hold whichever method is used stay
    applicable.
- exclusion: null unless the state is "not_applicable".
- reason: one sentence naming the function, attribute or fact the decision turns on.
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
                      instruction=INSTRUCTION, output_schema=GroupMatchBatch, tier="match", effort=effort,
                      settings=settings, tools=None if settings.cost_mode == "reduced" else [read_provision],
                      tool_call_limit=3)


def match_context(batch: MatchInput) -> list[tuple[str, str]]:
    card = batch.card
    obligations = "\n".join(
        f"[{o.obligation_id}] (paragraph {o.provision_id.split('#', 1)[1]}, {o.role}) {o.text}"
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
