"""`regulation_profiler`: one card per regulation version, so applicability can be decided
without reading the regulation (design spec section 6.1)."""

from __future__ import annotations

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.corpus.cards import CardPayload
from app.models import Issue, RegulationCard

INSTRUCTION = """\
You summarise one UN Regulation version into a regulation card. Another agent will read the cards of
all regulations to decide which ones apply to a product, without reading the regulation text, so the
card must say precisely what the regulation covers and where.

Fill the card from the text you are given only, never from memory:
- regulation, version_label, title: copy them from the payload.
- regulation_type: "device" if it approves a type of device or component (lamps, retro-reflectors,
  glazing, tyres, light sources); "installation" if it sets how devices are installed on a vehicle;
  "vehicle_system" if it approves a vehicle with regard to a system (braking, emissions, steering);
  "cross_cutting" if it applies to many kinds of component because of a property (for example
  electromagnetic compatibility of electrical/electronic sub-assemblies); otherwise "other".
- devices_in_scope: every device or component type the regulation approves or sets requirements for,
  named as an engineer would name it ("rear position lamp", "stop lamp", "reversing lamp").
- vehicle_categories: the vehicle categories named in its scope (M1, N1, L3, O, ...).
- functions_covered: the vehicle functions it covers ("rear position signalling", "braking indication").
- triggers: product properties that make it apply to a product that is not one of its devices,
  for example "contains electrical/electronic sub-assemblies". Empty when there are none.
- consolidates: the UN Regulations this one says it combines or replaces, written "UN R<number>".
  Only when the text says so.
- device_sections: for each device in scope, the provision ids of the sections that hold its
  requirements (technical requirements, markings, colour, photometry, test procedures and the
  annexes they use). Add an entry named "general" for sections that apply to every device (general
  specifications, markings, conformity of production). Use top-level or second-level ids from the
  table of contents.
- evidence: provision ids of the introduction, scope and definitions that support the card.

Use only provision ids that appear in the context. If the payload lists feedback, correct every issue.
"""


def create_regulation_profiler(settings: Settings) -> AgentSpec:
    return make_agent(name="regulation_profiler", description="Writes one regulation card per regulation version",
                      instruction=INSTRUCTION, output_schema=RegulationCard, tier="judgment", effort="medium",
                      settings=settings)


DEFINITIONS_LIMIT = 12000
INTRO_LIMIT = 4000  # a GTR's Introduction holds its whole rationale
PER_DEFINITION = 400


def build_profiler_prompt(payload: CardPayload, feedback: list[Issue]) -> str:
    store, v = payload.store, payload.version
    provisions = store.provisions(v.regulation, v.version_label)
    intro = next((p for p in provisions if p.paragraph == "Introduction"), None)
    scope = [p for p in provisions if p.kind == "scope"]
    definitions, used = [], 0
    for p in provisions:
        if p.kind != "definition" or used > DEFINITIONS_LIMIT:
            continue
        text = " ".join(p.text.split())[:PER_DEFINITION]
        definitions.append(f"[{p.provision_id}] {text}")
        used += len(text)
    toc = [f"{e.provision_id} | page {e.page} | {e.kind} | {e.heading[:90]}"
           for e in store.toc(v.regulation, v.version_label, 3) if e.kind != "form"]
    context = [
        ("Introduction", f"[{intro.provision_id}]\n{intro.text[:INTRO_LIMIT]}" if intro else "(none)"),
        ("Scope (exact text)", "\n\n".join(f"[{p.provision_id}]\n{p.text}" for p in scope) or "(none)"),
        ("Definitions (start of each)", "\n".join(definitions) or "(none)"),
        ("Table of contents (depth 3: provision id | page | kind | heading)", "\n".join(toc)),
    ]
    return render_prompt(
        task="Write the regulation card for this regulation version.",
        context=context,
        untrusted=[],
        payload={"regulation": v.regulation, "version_label": v.version_label, "title": v.title,
                 "scope_ids": [p.provision_id for p in scope], "feedback": [i.model_dump() for i in feedback]},
    )
