"""`extraction_verifier`: are the extracted obligations atomic, faithful and complete?"""

from __future__ import annotations

from app.agents.factory import AgentSpec, make_agent
from app.agents.obligation_extractor import render_provisions
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.matching.extraction import ExtractionBatch
from app.models import Obligation, Review

INSTRUCTION = """\
You check obligations extracted from regulation provisions against the provision text. Look for:
- two or more obligations merged into one ("merged");
- a value, unit, tolerance or condition added, changed or dropped ("unfaithful");
- an exception or condition of the source left out ("dropped_condition");
- a shall/must clause of the provision with no obligation ("missing");
- a subject that is unclear when the obligation is read on its own ("unclear_subject").

Return verdict "pass" when there is nothing to fix. Otherwise "retry" with one issue per problem:
type as above, target_id the provision id, reason saying exactly what to fix, evidence [], proposed null.
Do not rewrite the obligations yourself.
"""


def create_extraction_verifier(settings: Settings) -> AgentSpec:
    return make_agent(name="extraction_verifier", description="Checks extracted obligations against the source",
                      instruction=INSTRUCTION, output_schema=Review, tier="judgment", effort="low", settings=settings)


def build_extraction_review_prompt(batch: ExtractionBatch, obligations: list[Obligation]) -> str:
    return render_prompt(
        task="Check the extracted obligations against their provisions.",
        context=[("Provisions", render_provisions(batch))],
        untrusted=[],
        payload={"obligations": [
            {"obligation_id": o.obligation_id, "provision_id": o.provision_id, "text": o.text, "quote": o.quote,
             "condition": o.condition} for o in obligations]},
    )
