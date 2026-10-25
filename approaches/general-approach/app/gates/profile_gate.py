"""Code gate for the product profile (design spec section 6.3)."""

from __future__ import annotations

from app.corpus.parser import squash
from app.models import CaseInput, Issue, ProductProfile


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def profile_gate(case: CaseInput, profile: ProductProfile) -> list[Issue]:
    issues: list[Issue] = []
    if not profile.parts:
        return [_issue("no_parts", "profile", "the profile needs at least one part")]
    part_ids = [p.part_id for p in profile.parts]
    fact_ids = [f.fact_id for p in profile.parts for f in p.facts]
    for ids, what in ((part_ids, "part_id"), (fact_ids, "fact_id")):
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            issues.append(_issue("duplicate_id", dup, f"{what} {dup} is used more than once"))
    spec = squash(case.spec_text) if case.spec_text else None
    for part in profile.parts:
        for fact in part.facts:
            if fact.source == "spec":
                if spec is None:
                    issues.append(_issue("spec_fact_without_spec", fact.fact_id, "this case has no spec; use source drawing"))
                elif not fact.quote.strip() or squash(fact.quote) not in spec:
                    issues.append(_issue("quote_not_found", fact.fact_id,
                                         f"quote must be copied exactly from the spec: {fact.quote[:100]!r}"))
            elif not fact.quote.strip():
                issues.append(_issue("empty_quote", fact.fact_id, "a drawing fact needs the label as written"))
    return issues
