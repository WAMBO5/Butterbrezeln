"""Citation check (design spec section 7, output gate): every requirement's source must exist and
its quote must be on the cited page (±1), in the base version of a regulation in the index."""

from __future__ import annotations

from app.corpus.parser import squash
from app.corpus.store import CorpusStore
from app.models import Issue, Obligation, RegulationVersion, Requirement


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def quote_page(store: CorpusStore, regulation: str, version_label: str, quote: str, first: int, last: int) -> int | None:
    """The first page in `first..last` whose text (joined with the next page) holds the quote."""
    needle = squash(quote)
    if not needle:
        return None
    for page in range(first, last + 1):
        here = store.page_text(regulation, version_label, page) or ""
        nxt = store.page_text(regulation, version_label, page + 1) or ""
        if needle in squash(here):
            return page
        if needle in squash(here + nxt) and needle not in squash(nxt):
            return page
    return None


def check_citation(store: CorpusStore, req: Requirement, ob: Obligation, versions: list[RegulationVersion]) -> list[Issue]:
    s = req.source
    issues: list[Issue] = []
    known = [v for v in versions if v.regulation == s.regulation]
    if not known:
        return [_issue("unknown_regulation", req.id, f"{s.regulation} is not in regulations/index.json")]
    base = next((v for v in known if v.role == "base"), None)
    if base is None or s.version != base.version_label:
        issues.append(_issue("not_base_version", req.id, f"cite the base version of {s.regulation}"))
        return issues
    if store.page_text(s.regulation, s.version, s.page) is None:
        issues.append(_issue("page_missing", req.id, f"page {s.page} does not exist in {s.regulation} {s.version}"))
    if not s.paragraph or store.find(s.regulation, s.version, s.paragraph) is None:
        issues.append(_issue("paragraph_missing", req.id, f"paragraph {s.paragraph} not found"))
    window = "".join(store.page_text(s.regulation, s.version, p) or "" for p in (s.page - 1, s.page, s.page + 1))
    if not ob.quote.strip() or squash(ob.quote) not in squash(window):
        issues.append(_issue("quote_not_on_page", req.id, f"the quote is not on page {s.page} ±1"))
    return issues
