"""Code gate for `requirement_matcher` output (design spec section 6.5)."""

from __future__ import annotations

from app.matching.match import MatchInput
from app.models import Issue, MatchBatch


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def match_gate(batch: MatchInput, out: MatchBatch) -> list[Issue]:
    issues: list[Issue] = []
    wanted = [o.obligation_id for o in batch.obligations]
    facts = {f.fact_id for f in batch.part.facts}
    counts: dict[str, int] = {}
    for d in out.decisions:
        counts[d.obligation_id] = counts.get(d.obligation_id, 0) + 1
        if d.obligation_id not in wanted:
            issues.append(_issue("unknown_id", d.obligation_id, "not an obligation of this batch; copy ids exactly"))
            continue
        for ref in d.fact_refs:
            if ref not in facts:
                issues.append(_issue("unknown_fact", d.obligation_id, f"{ref} is not a fact of part {batch.part.part_id}"))
        if d.evidence_status == "not_met" and not d.fact_refs:
            issues.append(_issue("not_met_without_fact", d.obligation_id, "not_met needs the contradicting fact in fact_refs"))
    for oid in wanted:
        if counts.get(oid, 0) == 0:
            issues.append(_issue("missing_decision", oid, "decide every obligation"))
        elif counts[oid] > 1:
            issues.append(_issue("duplicate_decision", oid, "decide each obligation exactly once"))
    return issues
