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
- Split lists. When one shall governs a list of items ((a), (b), (c) ... or (i), (ii) ...) and each
  item binds on its own, write one obligation per item, repeating the subject and the shared
  condition, and quote the item's own words. Keep an "either ... or ..." or "at least one of the
  following" list in one obligation, since no single item binds.
- Tables. A sentence that names a test method or standard or points to a table ("shall be tested
  according to ... with the levels of Table 3", "shall meet the values in Table 4") is always an
  obligation of its own that names the table. For a table of test levels or limits per pulse, test,
  class or system voltage, also write one obligation per row. A light distribution or
  measuring-point table stays the single obligation that names it.
- Split a clause that sets independent constraints on different properties or subjects (for example
  a mounting height and, separately, a minimum distance to another device, or a rule for the main
  device and another for an optional one) into one obligation each; keep a range (minimum and
  maximum of the same quantity) in one obligation.
- Keep an exception or derogation in the same obligation as the rule it modifies ("..., except
  that ...", "however, ... may be reduced to ...", "(2,100 mm if ...)").
- Permissions on the product's design or installation are obligations too, when they stand on their
  own rather than as an exception to a rule of the same provision: a "may", "is permitted" or "is
  allowed" about what the product may have or do ("may be installed ... only if ...", "may have
  parts in common with ..."). Word it "... shall be permitted to ...", keeping every condition.
  A permission to choose a test method, an alternative test or a procedure is not an obligation.
- text: one self-contained sentence close to the source wording. Name the subject explicitly as the
  provision means it ("The rear position lamp shall ...", not "It shall ..."); keep every condition,
  exception, value, unit, tolerance and cross-reference ("as defined in paragraph 3.3.4.2."). Do not
  add requirements, merge clauses, or change values. At most 2,000 characters.
- quote: the exact words of the provision that state the obligation, copied verbatim and contiguous.
- subject, condition (null if none), constraint, quantities (value as written, unit, comparator
  such as "not less than", "at most", "±").
- kind: design, performance, marking, test, documentation or conformity.

No obligation (give no_obligation_reason): headings without requirements, definitions, statements
of when the authority grants or refuses approval, lists of form fields, and permissions that concern
the approval authority or the approval procedure rather than the product.

Use the referenced definitions only to name subjects correctly. If the payload lists feedback, fix
every issue it names.
"""


def create_obligation_extractor(settings: Settings) -> AgentSpec:
    return make_agent(name="obligation_extractor", description="Splits provisions into atomic obligations",
                      instruction=INSTRUCTION, output_schema=ExtractionOutput, tier="fast", effort="medium",
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
