"""Output gate (design spec sections 7 and 14.4): drop every requirement whose citation fails or
whose lineage is incomplete, then number the rest R-001, R-002, ..."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.compliance.lineage import Lineage, build_lineage, lineage_complete
from app.corpus.store import CorpusStore
from app.matching.citations import check_citation
from app.models import Issue, MatchDecision, Obligation, ProductProfile, RegulationVersion, Requirement, ScopePlan


@dataclass
class OutputContext:
    store: CorpusStore
    versions: list[RegulationVersion]
    profile: ProductProfile
    plan: ScopePlan
    obligations: dict[str, Obligation]
    decisions: list[MatchDecision]
    human_actions: list[dict] = field(default_factory=list)


def output_gate(reqs: list[Requirement], ctx: OutputContext) -> tuple[list[Requirement], list[Lineage], list[Issue]]:
    kept: list[Requirement] = []
    issues: list[Issue] = []
    for req in reqs:
        ob = ctx.obligations.get(req.obligation_ids[0]) if req.obligation_ids else None
        problems = check_citation(ctx.store, req, ob, ctx.versions) if ob is not None else []
        if ob is None or problems:
            reason = "; ".join(p.reason for p in problems) or "no obligation behind the requirement"
            issues.append(Issue(type="citation", target_id=req.obligation_ids[0] if req.obligation_ids else req.id,
                                reason=reason, evidence=[req.id], proposed=None))
            continue
        if not lineage_complete(build_lineage(req, ctx.profile, ctx.plan, ctx.obligations, ctx.decisions,
                                              ctx.human_actions)):
            issues.append(Issue(type="lineage", target_id=req.obligation_ids[0], reason="lineage is incomplete",
                                evidence=[req.id], proposed=None))
            continue
        kept.append(req)
    kept = [r.model_copy(update={"id": f"R-{n:03d}"}) for n, r in enumerate(kept, start=1)]
    lineages = [build_lineage(r, ctx.profile, ctx.plan, ctx.obligations, ctx.decisions, ctx.human_actions)
                for r in kept]
    return kept, lineages, issues
