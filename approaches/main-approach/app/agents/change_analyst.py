"""`change_analyst` (sub-goal): which old requirements change between two versions, and why
(design spec section 6.8). It sees only the provisions code marked changed."""

from __future__ import annotations

from typing import Any

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.models import ChangeOutput, Issue

INSTRUCTION = """\
You compare two versions of a UN Regulation. Code has paired the provisions, marked each pair
modified, added or removed, and described the textual edit. You also see the requirements derived
from the old version that cite each paragraph. Return the changes:
- "modified": a linked old requirement whose obligation the edit changes. requirement_id is its id;
  new_text is the requirement rewritten to the new wording, one obligation, close to the source.
- "removed": a linked old requirement whose provision was removed or no longer states it.
- "added": a new obligation that no old requirement covers (in an added provision, or a new clause in
  a modified one). requirement_id is null; new_text states it, one obligation per change.
- reason: which paragraph changed and how, quoting the old and new words ("'x' became 'y'").
- source: the page and paragraph of the new version (for removed: of the old version).
Leave out linked requirements the edit does not affect, and editorial changes that change no
obligation. Make no claim the texts do not support. If the payload lists feedback, fix every issue.
"""


def create_change_analyst(settings: Settings) -> AgentSpec:
    return make_agent(name="change_analyst", description="Explains which requirements change between versions",
                      instruction=INSTRUCTION, output_schema=ChangeOutput, tier="judgment", effort="medium",
                      settings=settings, max_tokens=32000)


def build_change_prompt(pairs: list[dict[str, Any]], case_id: str, feedback: list[Issue]) -> str:
    return render_prompt(
        task="Say which old requirements change, which are removed and which are added.",
        context=[], untrusted=[],
        payload={"case_id": case_id, "pairs": pairs, "feedback": [i.model_dump() for i in feedback]},
    )
