"""Code gate for `market_onboarding` (design spec section 6.6): every statement cited and found."""

from __future__ import annotations

from dataclasses import dataclass

from app.corpus.parser import squash
from app.models import Claim, Issue, MarketProfile, RegulationVersion, SourceRef

CONTEXT = 300


@dataclass(frozen=True)
class SourceDoc:
    document_id: str
    text: str
    sample: bool


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def _found(ref: SourceRef, docs: dict[str, SourceDoc]) -> bool:
    doc = docs.get(ref.document_id)
    return doc is not None and bool(ref.quote.strip()) and squash(ref.quote) in squash(doc.text)


def market_gate(sources: list[SourceDoc], versions: list[RegulationVersion], profile: MarketProfile) -> list[Issue]:
    docs = {s.document_id: s for s in sources}
    known = {v.regulation for v in versions}
    issues: list[Issue] = []
    for r in profile.rules:
        if r.regulation not in known:
            issues.append(_issue("unknown_regulation", r.regulation, "not in regulations/index.json; list it under "
                                                                     "outside_corpus instead"))
        if r.source_ref is None:
            issues.append(_issue("uncited", r.regulation, "every rule needs a source_ref with a quote"))
        elif not _found(r.source_ref, docs):
            issues.append(_issue("quote_not_found", r.regulation,
                                 f"the quote is not in document {r.source_ref.document_id}; copy it exactly"))
    for n, ref in enumerate(profile.outside_corpus, start=1):
        if not _found(ref, docs):
            issues.append(_issue("quote_not_found", f"outside_corpus:{n}", "the quote is not in its source document"))
    if any(s.sample for s in sources) and not profile.illustrative:
        issues.append(_issue("not_illustrative", profile.market_id, "a source is an illustrative sample; set illustrative"))
    return issues


def _context(ref: SourceRef, docs: dict[str, SourceDoc]) -> str:
    doc = docs.get(ref.document_id)
    if doc is None:
        return ref.quote
    pos = doc.text.find(ref.quote[:40])
    if pos < 0:
        return ref.quote
    return doc.text[max(0, pos - CONTEXT // 2): pos + len(ref.quote) + CONTEXT // 2]


def market_claims(sources: list[SourceDoc], profile: MarketProfile) -> list[Claim]:
    docs = {s.document_id: s for s in sources}
    claims = [Claim(claim_id=f"rule:{r.regulation}", text=f"{profile.name} treats {r.regulation} as {r.status} "
                                                            f"({r.version_role} version)",
                    cited_text=f"{r.source_ref.quote}\n\n{_context(r.source_ref, docs)}")
              for r in profile.rules if r.source_ref is not None]
    claims += [Claim(claim_id=f"outside:{n}", text=f"{profile.name} has a rule outside the UN corpus: {ref.quote}",
                     cited_text=_context(ref, docs)) for n, ref in enumerate(profile.outside_corpus, start=1)]
    return claims
