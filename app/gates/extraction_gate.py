"""Code gate for `obligation_extractor` output (design spec section 6.2)."""

from __future__ import annotations

import re

from app.corpus.parser import squash
from app.matching.extraction import ExtractionBatch
from app.models import TEXT_LIMIT, ExtractionOutput, Issue, ProvisionObligations

MODAL_RE = re.compile(r"\b(shall|must)\b", re.I)
# A list item marker at an item boundary: "(a) ", "(ii) " after the start, whitespace or ":" / ";".
ITEM_RE = re.compile(r"(?:^|(?<=[\s:;]))\(([a-z]|[ivx]{1,4})\)\s+")
ITEM_PREFIX = 40  # squashed characters of an item that some obligation's quote must contain
ITEM_NAME = 20  # or: squashed characters of the item, without a leading article, that some obligation's text names
ARTICLE_RE = re.compile(r"^(?:a|an|the|if|where|when)\s+", re.I)


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


def list_items(text: str) -> list[tuple[str, str]]:
    """The enumerated items of a provision as (marker, text), when it lists at least two starting at
    (a) or (i); [] otherwise."""
    marks = list(ITEM_RE.finditer(text))
    if len(marks) < 2 or marks[0].group(1) not in ("a", "i"):
        return []
    return [(m.group(1), text[m.end():marks[n + 1].start() if n + 1 < len(marks) else len(text)])
            for n, m in enumerate(marks)]


def missing_list_items(batch: ExtractionBatch, item: ProvisionObligations) -> list[Issue]:
    """List items of the provision that no obligation covers (a quote holding the item's start, a quote
    inside the item, or a text naming it): each binding item needs its own obligation, or the whole list
    one obligation for either/or lists. Not an `item_issues` check, so a false alarm costs a retry,
    never the provision."""
    p = next((x for x in batch.provisions if x.provision_id == item.provision_id), None)
    if p is None or not item.obligations:
        return []
    quotes = [squash(o.quote) for o in item.obligations]
    texts = [squash(o.text) for o in item.obligations]

    def covered(body: str) -> bool:
        whole = squash(body)
        named = squash(ARTICLE_RE.sub("", body.strip()))[:ITEM_NAME]
        return (not whole or any(whole[:ITEM_PREFIX] in q for q in quotes)
                or any(len(q) >= 15 and q in whole for q in quotes) or any(named in t for t in texts))

    missing = [mark for mark, body in list_items(p.text) if not covered(body)]
    if not missing:
        return []
    return [_issue("missing_list_item", p.provision_id,
                   f"list item(s) {', '.join(f'({m})' for m in missing)} have no obligation: write one obligation "
                   "per item that binds on its own, quoting the item's words, or one obligation quoting the whole "
                   "list when no single item binds (either/or)")]


def extraction_gate(batch: ExtractionBatch, out: ExtractionOutput) -> list[Issue]:
    issues: list[Issue] = []
    seen = set()
    for item in out.items:
        seen.add(item.provision_id)
        issues += item_issues(batch, item) + missing_list_items(batch, item)
    for p in batch.provisions:
        if p.provision_id not in seen:
            issues.append(_issue("missing_item", p.provision_id, "every provision in the batch needs an item"))
    return issues
