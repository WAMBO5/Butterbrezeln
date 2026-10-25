"""Code gate for `requirement_matcher` output (design spec section 6.5)."""

from __future__ import annotations

from app.matching.match import MatchInput
from app.models import GroupMatchBatch, Issue


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def match_gate(batch: MatchInput, out: GroupMatchBatch) -> list[Issue]:
    issues: list[Issue] = []
    wanted = [o.obligation_id for o in batch.obligations]
    group = set(batch.part_ids)
    facts = {f.fact_id for p in batch.parts for f in p.facts}
    counts: dict[str, int] = {}
    for d in out.decisions:
        counts[d.obligation_id] = counts.get(d.obligation_id, 0) + 1
        if d.obligation_id not in wanted:
            issues.append(_issue("unknown_id", d.obligation_id, "not an obligation of this batch; copy ids exactly"))
            continue
        for pid in d.part_ids:
            if pid not in group:
                issues.append(_issue("unknown_part", d.obligation_id, f"{pid} is not one of this batch's parts"))
        if d.state != "not_applicable" and not d.part_ids:
            issues.append(_issue("no_parts", d.obligation_id, f"name the parts it binds when it is {d.state}"))
        if d.state == "not_applicable" and d.exclusion is None:
            issues.append(_issue("no_exclusion", d.obligation_id, "not_applicable needs an exclusion (other_function, "
                                 "other_class, other_vehicle, shown_absent, presence_only); otherwise decide uncertain"))
        if d.state == "not_applicable" and d.exclusion == "shown_absent" and not d.fact_refs:
            issues.append(_issue("absent_without_fact", d.obligation_id, "shown_absent needs the fact that shows it"))
        for ref in d.fact_refs:
            if ref not in facts:
                issues.append(_issue("unknown_fact", d.obligation_id, f"{ref} is not a fact of these parts"))
        if d.evidence_status == "not_met" and not d.fact_refs:
            issues.append(_issue("not_met_without_fact", d.obligation_id, "not_met needs the contradicting fact in fact_refs"))
    for oid in wanted:
        if counts.get(oid, 0) == 0:
            issues.append(_issue("missing_decision", oid, "decide every obligation"))
        elif counts[oid] > 1:
            issues.append(_issue("duplicate_decision", oid, "decide each obligation exactly once"))
    return issues
