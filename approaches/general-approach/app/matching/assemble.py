"""Assembly (design spec section 7): one requirement per obligation, parts merged, cited to the
base version, page and paragraph, numbered R-001, R-002, ..."""

from __future__ import annotations

from app.corpus.parser import paragraph_key
from app.corpus.store import CorpusStore
from app.matching.citations import quote_page
from app.models import MatchDecision, Obligation, Requirement, Source

_EVIDENCE_RANK = {"met": 0, "evidence_needed": 1, "not_met": 2}


def _label(paragraph: str) -> str:
    return paragraph.split("~")[0]


def _sort_key(r: Requirement) -> tuple:
    key = paragraph_key(r.source.paragraph) or ""
    parts = tuple(int(n) if n.isdigit() else 0 for n in key.replace(" ", ".").split(".") if n)
    return (r.source.regulation, r.source.page, parts, key, r.text)


def assemble(decisions: list[MatchDecision], obligations: dict[str, Obligation], store: CorpusStore,
             include_uncertain: bool) -> list[Requirement]:
    states = ("applicable", "uncertain") if include_uncertain else ("applicable",)
    grouped: dict[str, list[MatchDecision]] = {}
    for d in decisions:
        if d.state in states and d.obligation_id in obligations:
            grouped.setdefault(d.obligation_id, []).append(d)
    reqs: list[Requirement] = []
    for oid, ds in grouped.items():
        ob = obligations[oid]
        p = store.get(ob.provision_id)
        if p is None:
            continue
        page = quote_page(store, p.regulation, p.version_label, ob.quote, p.page_start, p.page_end) or p.page_start
        first = ds[0]
        reqs.append(Requirement(
            id="", text=ob.text,
            source=Source(regulation=p.regulation, version=p.version_label, page=page, paragraph=_label(p.paragraph)),
            part_ids=sorted({d.part_id for d in ds}), obligation_ids=[oid],
            state="applicable" if any(d.state == "applicable" for d in ds) else "uncertain",
            reason=first.reason,
            evidence_status=max((d.evidence_status for d in ds), key=_EVIDENCE_RANK.__getitem__),
            test_case=first.test_case or None,
        ))
    reqs.sort(key=_sort_key)
    return [r.model_copy(update={"id": f"R-{n:03d}"}) for n, r in enumerate(reqs, start=1)]
