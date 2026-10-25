"""Matching batches and the final decision per part and obligation.

A batch is one section's candidate obligations for the group of parts the scope plan assigned that
section to: the matcher decides each obligation once and names the parts it binds, so the cost
grows with obligations, not with obligations × parts. Code expands the result to one
`MatchDecision` per part.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.corpus.store import CorpusStore
from app.matching.collect import SectionCandidates
from app.models import GroupMatchBatch, MatchDecision, Obligation, Part, ProductProfile, Provision, RegulationCard
from app.pipeline.loop import LoopResult

# Roles that are product requirements. `procedure` (how a laboratory runs a test) and `administrative`
# (approval procedure) are decided by code, the same way for every product, and never reach the matcher.
KEPT_ROLES = frozenset({"outcome", "outcome_condition", "design_rule", "permission"})


@dataclass
class MatchInput:
    parts: list[Part]
    product_summary: dict
    card: RegulationCard
    heading_path: list[str]
    obligations: list[Obligation]
    definitions: list[Provision]
    regulation: str = ""
    section_id: str = ""

    @property
    def part_ids(self) -> list[str]:
        return [p.part_id for p in self.parts]


def product_summary(profile: ProductProfile, part_ids: list[str]) -> dict:
    return {"product_type": profile.product_type, "vehicle_categories": profile.vehicle_categories,
            "other_parts": [p.name for p in profile.parts if p.part_id not in part_ids]}


def _placeholder(regulation: str, version_label: str) -> RegulationCard:
    return RegulationCard(regulation=regulation, version_label=version_label, title=regulation,
                          regulation_type="other", devices_in_scope=[], vehicle_categories=[], functions_covered=[],
                          triggers=[], consolidates=[], device_sections=[], evidence=[])


def make_match_batches(cands: list[SectionCandidates], obligations_by_provision: dict[str, list[Obligation]],
                       profile: ProductProfile, cards: list[RegulationCard], store: CorpusStore,
                       max_size: int) -> list[MatchInput]:
    parts = {p.part_id: p for p in profile.parts}
    by_reg = {c.regulation: c for c in cards}
    groups: dict[tuple[str, tuple[str, ...]], tuple[SectionCandidates, list[str]]] = {}
    for c in cands:
        if c.part_id not in parts:
            continue
        key = (c.section_id, tuple(p.provision_id for p in c.provisions))
        if key in groups:
            groups[key][1].append(c.part_id)
        else:
            groups[key] = (c, [c.part_id])
    batches: list[MatchInput] = []
    for c, part_ids in groups.values():
        obligations = [o for p in c.provisions for o in obligations_by_provision.get(p.provision_id, [])
                       if o.role in KEPT_ROLES]
        if not obligations:
            continue
        defs: dict[str, Provision] = {}
        for p in c.provisions:
            for ref in p.refs:
                target = store.get(ref) if "#" in ref else None
                if target is not None and target.kind == "definition":
                    defs.setdefault(target.provision_id, target)
        card = by_reg.get(c.regulation) or _placeholder(c.regulation, c.version_label)
        group = [parts[pid] for pid in dict.fromkeys(part_ids)]
        for start in range(0, len(obligations), max_size):
            batches.append(MatchInput(parts=group, product_summary=product_summary(profile, part_ids), card=card,
                                      heading_path=c.heading_path, obligations=obligations[start:start + max_size],
                                      definitions=list(defs.values()), regulation=c.regulation,
                                      section_id=c.section_id))
    return batches


def role_decisions(cands: list[SectionCandidates],
                   obligations_by_provision: dict[str, list[Obligation]]) -> list[MatchDecision]:
    """A not_applicable decision per part for every candidate obligation whose role is no product
    requirement, so it stays in the lineage instead of disappearing."""
    out: dict[tuple[str, str], MatchDecision] = {}
    for c in cands:
        for p in c.provisions:
            for o in obligations_by_provision.get(p.provision_id, []):
                if o.role not in KEPT_ROLES and (c.part_id, o.obligation_id) not in out:
                    out[(c.part_id, o.obligation_id)] = MatchDecision(
                        part_id=c.part_id, obligation_id=o.obligation_id, state="not_applicable",
                        reason=f"not a product requirement: role {o.role}", fact_refs=[],
                        evidence_status="evidence_needed", test_case="")
    return list(out.values())


def resolve(batch: MatchInput, result: LoopResult[GroupMatchBatch]) -> list[MatchDecision]:
    """One decision per part and obligation. A disagreement left at the end becomes `uncertain` with
    both reasons; an obligation the matcher never decided is `uncertain` ("no decision") for every
    part of the group."""
    wanted = {o.obligation_id for o in batch.obligations}
    group = batch.part_ids
    decided = {}
    if result.output is not None:
        for d in result.output.decisions:
            if d.obligation_id in wanted and d.obligation_id not in decided:
                decided[d.obligation_id] = d
    disputed = {i.target_id: i for i in result.open_issues} if not result.resolved else {}
    out: list[MatchDecision] = []
    for o in batch.obligations:
        d = decided.get(o.obligation_id)
        if d is None:
            out += [MatchDecision(part_id=pid, obligation_id=o.obligation_id, state="uncertain", reason="no decision",
                                  fact_refs=[], evidence_status="evidence_needed", test_case="") for pid in group]
            continue
        bound = [pid for pid in d.part_ids if pid in group] if d.state != "not_applicable" else []
        issue = disputed.get(o.obligation_id)
        for pid in group:
            state = d.state if pid in bound else "not_applicable"
            reason = d.reason if pid in bound or d.state == "not_applicable" else f"does not bind this part: {d.reason}"
            if d.state == "not_applicable" and d.exclusion:
                reason = f"{d.exclusion}: {reason}"
            if issue is not None:
                state, reason = "uncertain", f"{d.reason} | reviewer: {issue.reason}"
            out.append(MatchDecision(part_id=pid, obligation_id=o.obligation_id, state=state, reason=reason,
                                     fact_refs=d.fact_refs, evidence_status=d.evidence_status, test_case=d.test_case))
    return out
