"""`change_analyst` (sub-goal): which old requirements change between two versions, and why
(design spec section 6.8). It sees only the provisions code marked changed."""

from __future__ import annotations

from typing import Any

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.models import ChangeOutput, Issue

INSTRUCTION = """\
You compare two versions of a UN Regulation. Code has paired the provisions, also renumbered ones
(old_paragraph and new_paragraph then differ), marked each pair modified, added or removed, and
described the word-level edit. The pairs come in paragraph order, so a provision is followed by the
parts split off from it or added after it. You also see the requirements derived from the old version
that cite each paragraph. Return the changes:
- "modified": a linked old requirement when a word of the text it was derived from was added,
  dropped or replaced, also by a wording-only edit that changes no obligation (but not by a change of
  notation, see below), or when a sentence of the same provision that qualifies it (a condition,
  exception, scope or permitted deviation) was changed or added: such a sentence modifies every
  linked requirement whose obligation it restricts, exempts or conditions, not only the nearest one.
  Also when the requirement moved to another provision shown. requirement_id is its id; new_text is
  the requirement rewritten to the new wording, one obligation, close to the source.
- "removed": a linked old requirement whose obligation no provision shown states any more. A pair can
  join two unrelated provisions under one paragraph number: judge by the texts, not by the status or
  the edit; the old requirement is then removed and the new provision's obligations are added. An
  obligation that moved into a split-off or neighbouring provision is not removed.
- "added": each new obligation that no old requirement covers (in an added provision, or a new
  sentence, list item or table row in a modified one); text that only moved is not added. Look for
  them wherever the old requirements come from, Introduction paragraphs and tables included, also in
  statements without "shall" ("is only permitted when", "are not required to"). requirement_id is
  null; new_text states it, one obligation per change, split as the old requirements are split (each
  step of a procedure, each table row and each sentence with its own "shall" or "may" on its own).
- reason, for modified: "Paragraph <new> (formerly <old>, only when renumbered) of <regulation> was
  amended in version <new version>: 'x' became 'y'; 'z' was added." quoting the changed words of the
  requirement's own text or of the sentence qualifying it; say so when the edit is wording only. For
  removed: "Paragraph <old> of <regulation> was amended in version <new version>; the provision
  '<old words>' no longer appears." For added: "Paragraph <new> of <regulation> is new in version
  <new version>: '<new words>'." (or "was amended in version <new version>: '<new words>' was added").
- source: the page and paragraph of the new version where the obligation now is (for removed: of
  the old version).
Leave out a linked requirement only when its own words and the sentences qualifying it are unchanged,
also when its provision was moved or renumbered or other sentences of it changed. Notation changes
are not edits: a heading put before the text, a unit, number or symbol written another way ('s' for
'seconds', 'per cent' for '%', digits for a number word), spelling, hyphenation, capitals,
punctuation, footnote numbers. Make no claim the texts do not support. If the payload lists feedback,
fix every issue.
"""


def create_change_analyst(settings: Settings) -> AgentSpec:
    return make_agent(name="change_analyst", description="Explains which requirements change between versions",
                      instruction=INSTRUCTION, output_schema=ChangeOutput, tier="judgment", effort="medium",
                      settings=settings, max_tokens=32000)


def build_change_prompt(pairs: list[dict[str, Any]], case_id: str, feedback: list[Issue], regulation: str = "",
                        versions: tuple[str, str] = ("", "")) -> str:
    return render_prompt(
        task="Say which old requirements change, which are removed and which are added.",
        context=[], untrusted=[],
        payload={"case_id": case_id, "regulation": regulation, "old_version": versions[0],
                 "new_version": versions[1], "pairs": pairs, "feedback": [i.model_dump() for i in feedback]},
    )
