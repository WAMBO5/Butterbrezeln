"""Code gate for `obligation_extractor` output (design spec section 6.2)."""

from __future__ import annotations

import re

from app.corpus.parser import squash
from app.matching.extraction import ExtractionBatch
from app.models import TEXT_LIMIT, ExtractionOutput, Issue, ProvisionObligations

MODAL_RE = re.compile(r"\b(shall|must)\b", re.I)


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def item_issues(batch: ExtractionBatch, item: ProvisionObligations) -> list[Issue]:
    """Issues of one provision's item; [] means it can be cached on its own."""
    by_id = {p.provision_id: p for p in batch.provisions}
    p = by_id.get(item.provision_id)
    if p is None:
        return [_issue("unknown_id", item.provision_id, f"{item.provision_id} is not in this batch")]
    issues: list[Issue] = []
    if not item.obligations and not (item.no_obligation_reason or "").strip():
        issues.append(_issue("empty_item", p.provision_id, "give at least one obligation or a no_obligation_reason"))
    source = squash(p.text)
    for n, o in enumerate(item.obligations, start=1):
        target = f"{p.provision_id}/{n}"
        if not o.quote.strip() or squash(o.quote) not in source:
            issues.append(_issue("quote_not_found", target,
                                 f"quote must be copied exactly from the provision text: {o.quote[:120]!r}"))
        if len(o.text) > TEXT_LIMIT:
            issues.append(_issue("too_long", target, f"text has {len(o.text)} characters; the limit is {TEXT_LIMIT}"))
        if len(MODAL_RE.findall(o.text)) >= 3:
            issues.append(_issue("merged", target, "text holds 3 or more shall/must clauses; split it, one per obligation"))
    return issues


def extraction_gate(batch: ExtractionBatch, out: ExtractionOutput) -> list[Issue]:
    issues: list[Issue] = []
    seen = set()
    for item in out.items:
        seen.add(item.provision_id)
        issues += item_issues(batch, item)
    for p in batch.provisions:
        if p.provision_id not in seen:
            issues.append(_issue("missing_item", p.provision_id, "every provision in the batch needs an item"))
    return issues
