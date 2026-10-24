"""Matching batches (one part × one section) and the final decision per obligation."""

from __future__ import annotations

from dataclasses import dataclass

from app.corpus.store import CorpusStore
from app.matching.collect import SectionCandidates
from app.models import MatchBatch, MatchDecision, Obligation, Part, ProductProfile, Provision, RegulationCard
from app.pipeline.loop import LoopResult


@dataclass
class MatchInput:
    part: Part
    product_summary: dict
    card: RegulationCard
    heading_path: list[str]
    obligations: list[Obligation]
    definitions: list[Provision]
    regulation: str = ""
    section_id: str = ""


def product_summary(profile: ProductProfile, part_id: str) -> dict:
    return {"product_type": profile.product_type, "vehicle_categories": profile.vehicle_categories,
            "other_parts": [p.name for p in profile.parts if p.part_id != part_id]}


def _placeholder(regulation: str, version_label: str) -> RegulationCard:
    return RegulationCard(regulation=regulation, version_label=version_label, title=regulation,
                          regulation_type="other", devices_in_scope=[], vehicle_categories=[], functions_covered=[],
                          triggers=[], consolidates=[], device_sections=[], evidence=[])


def make_match_batches(cands: list[SectionCandidates], obligations_by_provision: dict[str, list[Obligation]],
                       profile: ProductProfile, cards: list[RegulationCard], store: CorpusStore,
                       max_size: int) -> list[MatchInput]:
    parts = {p.part_id: p for p in profile.parts}
    by_reg = {c.regulation: c for c in cards}
    batches: list[MatchInput] = []
    for c in cands:
        part = parts.get(c.part_id)
        obligations = [o for p in c.provisions for o in obligations_by_provision.get(p.provision_id, [])]
        if part is None or not obligations:
            continue
        defs: dict[str, Provision] = {}
        for p in c.provisions:
            for ref in p.refs:
                target = store.get(ref) if "#" in ref else None
                if target is not None and target.kind == "definition":
                    defs.setdefault(target.provision_id, target)
        card = by_reg.get(c.regulation) or _placeholder(c.regulation, c.version_label)
        for start in range(0, len(obligations), max_size):
            batches.append(MatchInput(part=part, product_summary=product_summary(profile, part.part_id), card=card,
                                      heading_path=c.heading_path, obligations=obligations[start:start + max_size],
                                      definitions=list(defs.values()), regulation=c.regulation,
                                      section_id=c.section_id))
    return batches


def resolve(batch: MatchInput, result: LoopResult[MatchBatch]) -> list[MatchDecision]:
    """One decision per obligation. A disagreement left at the end becomes `uncertain` with both
    reasons; an obligation the matcher never decided becomes `uncertain` ("no decision")."""
    wanted = {o.obligation_id for o in batch.obligations}
    decided: dict[str, MatchDecision] = {}
    if result.output is not None:
        for d in result.output.decisions:
            if d.obligation_id in wanted and d.obligation_id not in decided:
                decided[d.obligation_id] = d.model_copy(update={"part_id": batch.part.part_id})
    if not result.resolved:
        for issue in result.open_issues:
            d = decided.get(issue.target_id)
            if d is not None:
                decided[issue.target_id] = d.model_copy(
                    update={"state": "uncertain", "reason": f"{d.reason} | reviewer: {issue.reason}"})
    return [decided.get(o.obligation_id) or MatchDecision(
        part_id=batch.part.part_id, obligation_id=o.obligation_id, state="uncertain", reason="no decision",
        fact_refs=[], evidence_status="evidence_needed", test_case="") for o in batch.obligations]
