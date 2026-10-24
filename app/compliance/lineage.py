"""Requirement lineage (design spec section 14.4): product fact → scope decision → provision →
obligation → match decision → requirement, plus human actions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.models import MatchDecision, Obligation, ProductProfile, Requirement, ScopePlan

Step = Literal["part", "fact", "scope_decision", "provision", "obligation", "match_decision", "human_action"]
REQUIRED: set[str] = {"part", "scope_decision", "provision", "obligation", "match_decision"}


class LineageLink(BaseModel):
    step: Step
    ref: str
    summary: str


class Lineage(BaseModel):
    requirement_id: str
    links: list[LineageLink]


def build_lineage(req: Requirement, profile: ProductProfile, plan: ScopePlan, obligations: dict[str, Obligation],
                  decisions: list[MatchDecision], human_actions: list[dict]) -> Lineage:
    links: list[LineageLink] = []
    parts = {p.part_id: p for p in profile.parts}
    facts = {f.fact_id: f for p in profile.parts for f in p.facts}
    mine = [d for d in decisions if d.obligation_id in req.obligation_ids and d.part_id in req.part_ids]
    for pid in req.part_ids:
        if pid in parts:
            links.append(LineageLink(step="part", ref=pid, summary=parts[pid].name))
    for fid in dict.fromkeys(f for d in mine for f in d.fact_refs):
        if fid in facts:
            links.append(LineageLink(step="fact", ref=fid, summary=f"{facts[fid].key}: {facts[fid].value} "
                                                                   f"({facts[fid].source}: {facts[fid].quote[:120]})"))
    decision = next((d for d in plan.decisions if d.regulation == req.source.regulation
                     and d.state in ("applicable", "uncertain")), None)
    if decision is not None:
        links.append(LineageLink(step="scope_decision", ref=decision.regulation,
                                 summary=f"{decision.state} via {decision.path}: {decision.reason}"))
    for oid in req.obligation_ids:
        ob = obligations.get(oid)
        if ob is None:
            continue
        links.append(LineageLink(step="provision", ref=ob.provision_id,
                                 summary=f"{req.source.regulation} {req.source.version} page {req.source.page}, "
                                         f"paragraph {req.source.paragraph}"))
        links.append(LineageLink(step="obligation", ref=oid,
                                 summary=f"quote: {ob.quote[:200]} (extractor {ob.extractor_version}, "
                                         f"{'verified' if ob.verified else 'unverified'})"))
    for d in mine:
        links.append(LineageLink(step="match_decision", ref=f"{d.part_id}:{d.obligation_id}",
                                 summary=f"{d.state}, evidence {d.evidence_status}: {d.reason}"))
    for a in human_actions:
        if a.get("target_id") in {req.id, req.source.regulation, *req.obligation_ids}:
            links.append(LineageLink(step="human_action", ref=f"{a.get('checkpoint')}:{a.get('action')}",
                                     summary=f"{a.get('reviewer')}: {a.get('reason') or ''}"))
    return Lineage(requirement_id=req.id, links=links)


def lineage_complete(lin: Lineage) -> bool:
    return REQUIRED <= {link.step for link in lin.links}
