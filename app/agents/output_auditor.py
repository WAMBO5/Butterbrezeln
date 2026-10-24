"""`output_auditor`: duplicates, merged obligations, unclear subjects, layout (spec section 6.9)."""

from __future__ import annotations

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.models import Requirement, Review

INSTRUCTION = """\
You audit the final list of engineering requirements drawn from UN Regulations. Each line has an id,
its citation, the parts it binds and its text. Report only these problems, one issue each:
- "duplicate": the requirement states the same obligation as another one (same scope, condition and
  constraint); target_id one of the two ids, evidence [the other id].
- "merged": the requirement holds two or more separate obligations.
- "unclear_subject": the subject cannot be understood without its paragraph ("It shall ...").
- "format": the paragraph label is malformed (labels look like "5.4.2", "Annex 8 2.1", "Annex 4 Part 1 1.2").
reason says what is wrong; proposed null. Return verdict "pass" with no issues when the list is clean.
Do not judge whether the requirements apply; that was decided earlier.
"""


def create_output_auditor(settings: Settings) -> AgentSpec:
    return make_agent(name="output_auditor", description="Audits the final requirement list",
                      instruction=INSTRUCTION, output_schema=Review, tier="judgment", effort="medium",
                      settings=settings, max_tokens=32000)


def build_output_audit_prompt(reqs: list[Requirement]) -> str:
    lines = "\n".join(f"{r.id} | {r.source.regulation} {r.source.version} p.{r.source.page} §{r.source.paragraph} | "
                      f"parts {','.join(r.part_ids)} | {r.text}" for r in reqs)
    return render_prompt(task="Audit this requirement list.", context=[("Requirements", lines)], untrusted=[],
                         payload={"requirement_ids": [r.id for r in reqs]})
