"""`scope_narrower`: decide every regulation, and the sections per part (design spec section 6.4)."""

from __future__ import annotations

import json

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.models import Issue, ProductProfile, RegulationCard, ScopePlan
from app.tools.corpus_tools import get_table_of_contents, read_provision, search_corpus

INSTRUCTION = """\
You decide which UN Regulations apply to a product, and which of their sections matter for each of
its parts. You get one card per regulation (below) and the product profile. With tools you can open a
regulation's table of contents, search all regulations, and read single provisions: at most 15 tool
calls in total, so use them to choose sections, not to read whole regulations.

A regulation applies by one of these paths; consider all of them for every part:
1. device: the regulation approves the part itself, or a device type the part is (path "device").
2. installation: the regulation sets how the part's function is installed on a vehicle; it applies to
   the component too (path "installation").
3. cross-cutting: a property of a part triggers it, for example electronics → electromagnetic
   compatibility (path "cross_cutting").
4. cross-reference: a kept section points to an annex, test procedure or definition; keep those too.
5. consolidation: an older regulation whose content a newer applicable regulation combines is
   not_applicable; name the newer one in the reason. Keep it only with a consolidation_override reason.

Rules:
- Decide every regulation in the cards: exactly one decision each, with the version_label of its card.
  state "applicable", "uncertain" (it may apply but the inputs do not settle it) or "not_applicable";
  path "device", "installation", "cross_cutting" or "none".
- A regulation limited to vehicle categories the product is not for is not_applicable.
- For applicable and uncertain decisions give part_ids and, for every listed part, the section ids
  (provision ids from a card's device_sections or a table of contents) that hold the requirements an
  engineer designs and tests that part to:
  - the markings section and the general requirements that bind every device of the regulation
    (general specifications, construction, colour, photometry, light sources, failure provisions),
    the conformity-of-production clause that sets the tolerances the product must hold (not its
    sampling procedure), and in an installation regulation its general installation provisions;
  - the device-specific sections only for the device types, classes or functions the part has (the
    stop lamp section for a stop lamp, not the direction-indicator section); a signal the vehicle
    produces by operating the part (an emergency stop or answer-back signal using its lamps) is not
    one of the part's own functions;
  - where the regulation has separate provisions for a vehicle and for a component (ESA, separate
    technical unit, device), the ones for the product's level; for a product that is a vehicle
    component approved with the vehicle (such as a bumper), the vehicle provisions that concern it;
  - an annex only when it sets limits, pass/fail criteria, or the test levels and exposure
    conditions the part must withstand (for example environmental resistance tests, or the impact
    test a kept requirement refers to: speeds, masses, heights, directions and impact points); leave out
    annexes that only describe how to set up and perform a measurement, give examples, diagrams or
    illustrations, measuring grids, sampling plans, approval-mark layouts or forms, even when a kept
    section refers to them.
  Prefer second-level ids (such as "5.2" or "Annex 6 Part 4") over whole chapters. Leave out the
  application and approval procedure, modifications and extensions, conformity-of-production
  sampling, penalties, transitional provisions, and sections for vehicle categories or device types
  the product is not.
- reason: one or two sentences that cite the card or a provision; evidence: the ids you relied on.
- parts_without_regulation: parts that no regulation covers.
- If the payload lists feedback (from the code gate or the recall auditor), answer every issue.
"""


def render_cards(cards: list[RegulationCard]) -> str:
    """One JSON line per card, sorted by regulation: byte-stable, so the prompt prefix caches."""
    return "\n".join(json.dumps(c.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                     for c in sorted(cards, key=lambda c: c.regulation))


def create_scope_narrower(settings: Settings, cards: list[RegulationCard]) -> AgentSpec:
    return make_agent(name="scope_narrower", description="Picks regulations and sections per part",
                      instruction=INSTRUCTION + "\n\n# Regulation cards\n" + render_cards(cards),
                      output_schema=ScopePlan, tier="judgment", effort="high", settings=settings,
                      tools=[get_table_of_contents, search_corpus, read_provision], tool_call_limit=15,
                      max_tokens=32000)


def build_scope_prompt(profile: ProductProfile, feedback: list[Issue]) -> str:
    return render_prompt(
        task="Write the scope plan for this product: one decision per regulation card.",
        context=[("Product profile", json.dumps(profile.model_dump(), indent=1, ensure_ascii=False))],
        untrusted=[],
        payload={"part_ids": [p.part_id for p in profile.parts], "feedback": [i.model_dump() for i in feedback]},
    )
