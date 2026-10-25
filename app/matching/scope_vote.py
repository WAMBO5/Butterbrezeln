"""Merge independent scope samples by vote (code only).

The scope draw is the run's largest random factor, so several `scope_narrower` samples run
independently and code merges them: a regulation is kept when a majority of the samples keep it
(one wrong regulation can add a hundred false requirements), and is `applicable` when a majority say
so, otherwise `uncertain`. Its sections per part are the union over the samples that kept it: a
missed section loses recall at every later step, while extra sections are pruned by the role filter
and the matcher.
"""

from __future__ import annotations

from collections import Counter

from app.models import PartSections, RegulationDecision, ScopePlan

KEPT = ("applicable", "uncertain")


def majority(n: int) -> int:
    """Samples needed to keep a regulation: 2 of 3, 2 of 2, 1 of 1."""
    return n // 2 + 1


def _union_sections(decisions: list[RegulationDecision]) -> list[PartSections]:
    by_part: dict[str, list[str]] = {}
    for d in decisions:
        for s in d.sections:
            ids = by_part.setdefault(s.part_id, [])
            ids += [i for i in s.section_ids if i not in ids]
    return [PartSections(part_id=pid, section_ids=ids) for pid, ids in by_part.items()]


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
            decisions.append(RegulationDecision(
                regulation=regulation, version_label=first.version_label,
                state="applicable" if len(applicable) >= need else "uncertain",
                path=Counter(d.path for d in kept).most_common(1)[0][0],
                part_ids=list(dict.fromkeys(pid for d in kept for pid in d.part_ids)),
                sections=_union_sections(kept), reason=f"{first.reason} [scope vote: {votes[regulation]}]",
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
