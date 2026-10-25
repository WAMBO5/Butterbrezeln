"""Merge independent scope samples by vote (code only).

The scope draw is the run's largest random factor, so several `scope_narrower` samples run
independently and code merges them: a regulation is kept when a majority of the samples keep it
(one wrong regulation can add a hundred false requirements), and is `applicable` when a majority say
so, otherwise `uncertain`. A section is kept the same way, when a majority of the samples chose it
or a section containing it (for any part; "5" contains "5.1", "Annex 6" contains "Annex 6 Part 4"),
and goes to every part a sample gave it to. On the rear-lamp dev run, requirements
from sections only 1 of 3 samples chose were 7 % on expert paragraphs, below F2's break-even of about
15 %; 2 of 3 gave 37 %. If no section of a kept regulation reaches a majority, the union is kept.
"""

from __future__ import annotations

from collections import Counter

from app.models import PartSections, RegulationDecision, ScopePlan

KEPT = ("applicable", "uncertain")


def majority(n: int) -> int:
    """Samples needed to keep a regulation: 2 of 3, 2 of 2, 1 of 1."""
    return n // 2 + 1


def within(child: str, parent: str) -> bool:
    """`UN R48@9.3.0#5.1` is within `UN R48@9.3.0#5`; `#Annex 6 Part 4` within `#Annex 6`; `#50` is not within `#5`."""
    if child == parent:
        return True
    reg, _, label = child.partition("#")
    preg, _, plabel = parent.partition("#")
    return reg == preg and label.startswith(plabel) and label[len(plabel):len(plabel) + 1] in (".", " ")


def _sections(decisions: list[RegulationDecision], need: int) -> list[PartSections]:
    """Sections that at least `need` samples chose, directly or through a section containing them,
    each with every part a sample gave it to; the union when none reaches `need`."""
    chosen = [{i for s in d.sections for i in s.section_ids} for d in decisions]
    support = {sid: sum(any(within(sid, c) for c in sample) for sample in chosen) for sid in set().union(*chosen)}
    keep = {sid for sid, n in support.items() if n >= need} or set(support)
    by_part: dict[str, list[str]] = {}
    for d in decisions:
        for s in d.sections:
            ids = by_part.setdefault(s.part_id, [])
            ids += [i for i in s.section_ids if i in keep and i not in ids]
    return [PartSections(part_id=pid, section_ids=ids) for pid, ids in by_part.items() if ids]


def merge_plans(plans: list[ScopePlan]) -> tuple[ScopePlan, dict[str, str]]:
    """The merged plan, and the votes of every regulation at least one sample kept ("2/3 kept, 1/3 applicable")."""
    if len(plans) == 1:
        return plans[0], {}
    n, need = len(plans), majority(len(plans))
    by_regulation: dict[str, list[RegulationDecision]] = {}
    for plan in plans:
        for d in plan.decisions:
            by_regulation.setdefault(d.regulation, []).append(d)
    decisions: list[RegulationDecision] = []
    votes: dict[str, str] = {}
    for regulation, ds in by_regulation.items():
        kept = [d for d in ds if d.state in KEPT]
        applicable = [d for d in ds if d.state == "applicable"]
        if kept:
            votes[regulation] = f"{len(kept)}/{n} kept, {len(applicable)}/{n} applicable"
        if len(kept) >= need:
            first = (applicable or kept)[0]
            sections = _sections(kept, need)
            decisions.append(RegulationDecision(
                regulation=regulation, version_label=first.version_label,
                state="applicable" if len(applicable) >= need else "uncertain",
                path=Counter(d.path for d in kept).most_common(1)[0][0],
                part_ids=[s.part_id for s in sections],
                sections=sections, reason=f"{first.reason} [scope vote: {votes[regulation]}]",
                evidence=list(dict.fromkeys(e for d in kept for e in d.evidence)),
                consolidation_override=next((d.consolidation_override for d in kept if d.consolidation_override), None)))
        else:
            first = kept[0] if kept else ds[0]
            prefix = f"kept by {len(kept)} of {n} scope samples only: " if kept else ""
            decisions.append(RegulationDecision(
                regulation=regulation, version_label=first.version_label, state="not_applicable", path="none",
                part_ids=[], sections=[], reason=f"{prefix}{first.reason}", evidence=first.evidence,
                consolidation_override=None))
    covered = {pid for d in decisions if d.state in KEPT for pid in d.part_ids}
    without = list(dict.fromkeys(pid for plan in plans for pid in plan.parts_without_regulation if pid not in covered))
    return ScopePlan(decisions=decisions, parts_without_regulation=without), votes
