"""Batches of provisions for `obligation_extractor`: one top-level section at a time."""

from __future__ import annotations

from dataclasses import dataclass

from app.corpus.store import CorpusStore
from app.models import Provision

EXTRACT_KINDS = {"requirement", "test_procedure", "conformity"}
OTHER_MIN_CHARS = 25


def extractable(p: Provision) -> bool:
    """Provisions that can hold an obligation: modal text, and table-style text such as
    "In height: not less than 250 mm" (kind `other`) that is longer than a bare heading."""
    return p.kind in EXTRACT_KINDS or (p.kind == "other" and len(" ".join(p.text.split())) >= OTHER_MIN_CHARS
                                       and p.paragraph != "Introduction")


@dataclass
class ExtractionBatch:
    section_id: str
    provisions: list[Provision]
    definitions: list[Provision]


def section_root(paragraph: str) -> str:
    """`5.4.2` → `5`; `Annex 4 Part 1 1.2` → `Annex 4`."""
    words = paragraph.split("~")[0].split(" ")
    if words[0] == "Annex" and len(words) > 1:
        return f"Annex {words[1]}"
    return words[0].split(".")[0]


def make_extraction_batches(provisions: list[Provision], store: CorpusStore, max_size: int) -> list[ExtractionBatch]:
    groups: dict[str, list[Provision]] = {}
    for p in provisions:
        if extractable(p):
            groups.setdefault(f"{p.regulation}@{p.version_label}#{section_root(p.paragraph)}", []).append(p)
    batches: list[ExtractionBatch] = []
    for section_id, members in groups.items():
        for start in range(0, len(members), max_size):
            chunk = members[start:start + max_size]
            defs: dict[str, Provision] = {}
            for p in chunk:
                for ref in p.refs:
                    target = store.get(ref) if "#" in ref else None
                    if target is not None and target.kind == "definition":
                        defs.setdefault(target.provision_id, target)
            batches.append(ExtractionBatch(section_id=section_id, provisions=chunk, definitions=list(defs.values())))
    return batches
