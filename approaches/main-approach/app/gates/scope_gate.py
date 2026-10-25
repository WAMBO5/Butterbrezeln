"""Code gate for the scope plan (design spec section 6.4)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.corpus.store import CorpusStore
from app.models import Issue, ProductProfile, RegulationCard, RegulationVersion, ScopePlan

KEPT = ("applicable", "uncertain")


@dataclass
class ScopeContext:
    profile: ProductProfile
    versions: list[RegulationVersion]  # base versions, one per regulation in the index
    cards: list[RegulationCard]
    store: CorpusStore


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def regulation_number(ref: str) -> str | None:
    """`"UN R148"`, `"Regulation No. 148"`, `"R148"` → `"148"`; GTRs keep their prefix."""
    m = re.search(r"GTR\s*(?:No\.\s*)?(\d+)", ref, re.I)
    if m:
        return f"GTR{m.group(1)}"
    m = re.search(r"(?:\bR|No\.\s*)(\d+[A-Z]?)\b", ref)
    return m.group(1) if m else None


def scope_gate(ctx: ScopeContext, plan: ScopePlan) -> list[Issue]:
    issues: list[Issue] = []
    base = {v.regulation: v.version_label for v in ctx.versions if v.role == "base"}
    part_ids = {p.part_id for p in ctx.profile.parts}
    counts: dict[str, int] = {}
    for d in plan.decisions:
        counts[d.regulation] = counts.get(d.regulation, 0) + 1
    for reg in sorted(base):
        if counts.get(reg, 0) == 0:
            issues.append(_issue("missing_decision", reg, f"decide {reg}: applicable, uncertain or not_applicable"))
        elif counts[reg] > 1:
            issues.append(_issue("duplicate_decision", reg, f"{reg} has {counts[reg]} decisions; give exactly one"))
    for reg in sorted(set(counts) - set(base)):
        issues.append(_issue("unknown_regulation", reg, f"{reg} is not in regulations/index.json"))

    covered: set[str] = set(plan.parts_without_regulation)
    for d in plan.decisions:
        if d.regulation not in base:
            continue
        if d.version_label != base[d.regulation]:
            issues.append(_issue("wrong_version", d.regulation,
                                 f"use the base version {base[d.regulation]}, not {d.version_label}"))
        for pid in set(d.part_ids) | {s.part_id for s in d.sections}:
            if pid not in part_ids:
                issues.append(_issue("unknown_part", f"{d.regulation}:{pid}", f"{pid} is not a part of the profile"))
        for ps in d.sections:
            for sid in ps.section_ids:
                p = ctx.store.get(sid)
                if p is None or p.regulation != d.regulation or p.version_label != base[d.regulation]:
                    issues.append(_issue("unknown_section", sid,
                                         f"{sid} is not a provision id of {d.regulation} {base[d.regulation]}"))
        if d.state in KEPT:
            covered |= set(d.part_ids)
            sections = {ps.part_id: ps.section_ids for ps in d.sections}
            for pid in d.part_ids:
                if not sections.get(pid):
                    issues.append(_issue("missing_sections", f"{d.regulation}:{pid}",
                                         f"list the sections of {d.regulation} that apply to part {pid}"))

    kept = {d.regulation: d for d in plan.decisions if d.state in KEPT}
    cards = {c.regulation: c for c in ctx.cards}
    for reg, d in kept.items():
        number = regulation_number(reg)
        for other in kept:
            card = cards.get(other)
            if other == reg or card is None or number is None:
                continue
            if any(regulation_number(c) == number for c in card.consolidates) and not (d.consolidation_override or "").strip():
                issues.append(_issue("consolidated", reg, f"{other} consolidates {reg}; drop {reg} or give a "
                                                          "consolidation_override reason"))
    for pid in sorted(part_ids - covered):
        issues.append(_issue("uncovered_part", pid, f"part {pid} has no applicable or uncertain regulation; "
                                                    "add one or list it in parts_without_regulation"))
    return issues
