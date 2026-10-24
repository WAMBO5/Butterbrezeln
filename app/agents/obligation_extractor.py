"""`obligation_extractor`: provisions → atomic obligations worded close to the source
(design spec section 6.2). It never sees a product."""

from __future__ import annotations

import json
from pathlib import Path

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.matching.extraction import ExtractionBatch
from app.models import ExtractionOutput, Issue

EXAMPLES_PATH = Path(__file__).with_name("examples") / "extraction_examples.json"

INSTRUCTION = """\
You turn provisions of a UN Regulation into atomic engineering obligations. For each provision in the
batch return exactly one item with its provision_id, and either its obligations or a short
no_obligation_reason.

Rules for an obligation:
- One obligation per requirement: one shall/must clause, or one requirement written in table style
  under a heading (for example "In height: not less than 250 mm" under "Position" of a lamp), which
  you state as a shall sentence.
- text: one self-contained sentence close to the source wording. Name the subject explicitly as the
  provision means it ("The rear position lamp shall ...", not "It shall ..."); keep every condition,
  exception, value, unit, tolerance and cross-reference ("as defined in paragraph x.y."). Do not
  add requirements, merge clauses, or change values. At most 2,000 characters.
- quote: the exact words of the provision that state the obligation, copied verbatim and contiguous.
- subject, condition (null if none), constraint, quantities (value as written, unit, comparator
  such as "not less than", "at most", "±").
- kind: design, performance, marking, test, documentation or conformity.

No obligation (give no_obligation_reason): headings without requirements, definitions, statements
of when the authority grants or refuses approval, lists of form fields, and permissions ("may") that
do not constrain anything.

Use the referenced definitions only to name subjects correctly. If the payload lists feedback, fix
every issue it names.
"""


def create_obligation_extractor(settings: Settings) -> AgentSpec:
    return make_agent(name="obligation_extractor", description="Splits provisions into atomic obligations",
                      instruction=INSTRUCTION, output_schema=ExtractionOutput, tier="fast", effort="low",
                      settings=settings)


def _examples() -> str:
    return json.dumps(json.loads(EXAMPLES_PATH.read_text(encoding="utf-8")), indent=1, ensure_ascii=False)


def render_provisions(batch: ExtractionBatch) -> str:
    blocks = []
    for p in batch.provisions:
        path = " > ".join(h[:80] for h in p.heading_path)
        blocks.append(f"[{p.provision_id}] paragraph {p.paragraph}, page {p.page_start}"
                      f"{' — under: ' + path if path else ''}\n{p.text}")
    return "\n\n".join(blocks)


def build_extraction_prompt(batch: ExtractionBatch, feedback: list[Issue]) -> str:
    definitions = "\n\n".join(f"[{d.provision_id}] {d.text}" for d in batch.definitions) or "(none)"
    return render_prompt(
        task="Extract the obligations of every provision below.",
        context=[("Worked examples (another regulation)", _examples()),
                 ("Referenced definitions", definitions),
                 ("Provisions", render_provisions(batch))],
        untrusted=[],
        payload={"section_id": batch.section_id, "provision_ids": [p.provision_id for p in batch.provisions],
                 "feedback": [i.model_dump() for i in feedback]},
    )
