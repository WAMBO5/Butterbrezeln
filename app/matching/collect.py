"""Candidate provisions per part and section: the scope plan's sections, plus the provisions they
reference (one level deep), each counted once per part (design spec section 7)."""

from __future__ import annotations

from dataclasses import dataclass

from app.corpus.store import CorpusStore
from app.gates.scope_gate import KEPT
from app.matching.extraction import extractable
from app.models import Provision, ScopePlan


@dataclass
class SectionCandidates:
    part_id: str
    regulation: str
    version_label: str
    section_id: str
    heading_path: list[str]
    provisions: list[Provision]


def _is_annex_heading(p: Provision) -> bool:
    words = p.paragraph.split(" ")
    return words[0] == "Annex" and len(words) == 2


def collect_candidates(store: CorpusStore, plan: ScopePlan) -> list[SectionCandidates]:
    out: list[SectionCandidates] = []
    seen: dict[str, set[str]] = {}
    for d in plan.decisions:
        if d.state not in KEPT:
            continue
        prefix = f"{d.regulation}@{d.version_label}#"
        for ps in d.sections:
            part_seen = seen.setdefault(ps.part_id, set())
            for sid in ps.section_ids:
                root = store.get(sid)
                if root is None:
                    continue
                chosen: list[Provision] = []

                def take(p: Provision) -> None:
                    if extractable(p) and p.provision_id not in part_seen:
                        part_seen.add(p.provision_id)
                        chosen.append(p)

                for p in store.provisions_under([sid]):
                    take(p)
                for p in list(chosen):
                    for ref in p.refs:
                        if not ref.startswith(prefix):
                            continue
                        target = store.get(ref)
                        if target is None or target.kind == "definition":
                            continue
                        for t in store.provisions_under([ref]) if _is_annex_heading(target) else [target]:
                            take(t)
                if chosen:
                    heading = root.text.split("\n", 1)[0][:120]
                    out.append(SectionCandidates(part_id=ps.part_id, regulation=d.regulation,
                                                 version_label=d.version_label, section_id=sid,
                                                 heading_path=[*root.heading_path, f"{root.paragraph} {heading}"],
                                                 provisions=chosen))
    return out
