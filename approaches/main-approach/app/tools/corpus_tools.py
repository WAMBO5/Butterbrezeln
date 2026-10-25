"""Read-only tools over the parsed corpus, for agents that explore regulations.

Plain functions: `app/llm.py` wraps them as SDK tools. Each returns a JSON-serialisable dict with a
`status` key, and an error message the model can act on when the input is wrong.
"""

from __future__ import annotations

from app.corpus.store import CorpusStore

_STORE: CorpusStore | None = None
TEXT_LIMIT = 6000
SNIPPET_LIMIT = 300


def bind_store(store: CorpusStore) -> None:
    """Point the tools at a built corpus store."""
    global _STORE
    _STORE = store


def _store() -> CorpusStore:
    if _STORE is None:
        raise RuntimeError("corpus tools used before bind_store()")
    return _STORE


def get_table_of_contents(regulation: str, depth: int) -> dict:
    """Table of contents of a UN Regulation (its base version): paragraph ids, headings and pages.

    Use it to find the sections of a regulation that cover a device or function before reading them.

    Args:
        regulation: The regulation id exactly as in the cards, for example "UN R148" or "UN GTR 9".
        depth: How deep to list paragraphs, 1 to 4 (1 = top-level sections and annexes only).
    """
    store = _store()
    version = store.base_version(regulation)
    if version is None:
        return {"status": "error", "message": f"unknown regulation: {regulation}"}
    depth = max(1, min(4, int(depth)))
    entries = [
        {"provision_id": e.provision_id, "paragraph": e.paragraph, "heading": e.heading, "page": e.page, "kind": e.kind}
        for e in store.toc(regulation, version.version_label, depth)
    ]
    return {"status": "ok", "regulation": regulation, "version_label": version.version_label, "entries": entries}


def search_corpus(query: str) -> dict:
    """Full-text search over the base versions of all regulations; returns the 10 best provisions.

    Use it to check whether a property or part (for example "electronic sub-assembly" or
    "retro-reflector") is regulated somewhere you have not looked yet.

    Args:
        query: Plain words to search for; words shorter than 3 letters are ignored.
    """
    hits = _store().search(query, 10, "base")
    return {
        "status": "ok",
        "hits": [
            {"provision_id": h.provision_id, "regulation": h.regulation, "paragraph": h.paragraph, "page": h.page,
             "snippet": h.snippet[:SNIPPET_LIMIT]}
            for h in hits
        ],
    }


def read_provision(provision_id: str) -> dict:
    """The exact text of one provision (paragraph), with its page and heading path.

    Args:
        provision_id: The id from a table of contents or search hit, for example "UN R148@1.6.0#5.4.2".
    """
    p = _store().get(provision_id)
    if p is None:
        return {"status": "error", "message": f"unknown provision id: {provision_id}; use an id from a table of contents or search hit"}
    data = p.model_dump()
    data["truncated"] = len(p.text) > TEXT_LIMIT
    data["text"] = p.text[:TEXT_LIMIT]
    return {"status": "ok", **data}


CORPUS_TOOLS = (get_table_of_contents, search_corpus, read_provision)
