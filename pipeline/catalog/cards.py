"""Regulation cards: title, version, scope text, and the predecessors a consolidated regulation supersedes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from pipeline.catalog.corpus import Version, base_versions, page_text, provisions

COMBINES = re.compile(r"combines the provisions of (?:the )?individual UN Regulations Nos\.\s*([\d,\sand]+?)\s+into", re.I | re.S)


@dataclass(frozen=True)
class Card:
    regulation: str
    title: str
    version_label: str
    scope: str
    supersedes: tuple[str, ...]  # e.g. ("UN R3", "UN R27", ...)


def supersedes(text: str) -> tuple[str, ...]:
    """Predecessors named in the Introduction: 'This Regulation combines the provisions of ... Nos. 4, 6, 7 ... into'."""
    m = COMBINES.search(" ".join(text[:6000].split()))
    if not m:
        return ()
    return tuple(f"UN R{n}" for n in re.findall(r"\d+", m.group(1)))


# Scope headings first ("1. Scope", "2. APPLICATION / SCOPE", "1. Field of application"); a purpose heading only if none exists.
# Not just "application": "2. Application for approval" is the type-approval procedure, not the scope.
SCOPE_HEADINGS = (re.compile(r"(?i)^[0-2]\.?\s*(?:scope|field of application|application\s*/\s*scope)\b"),
                  re.compile(r"(?i)^[0-2]\.?\s*(?:purpose|object)\b"))
BANNER = re.compile(r"(?s)^.*?Role in the hackathon:[^\n]*\n")
APPLIES_TO = re.compile(r"(?i)\b(?:applies|apply) to\b")


def _scope(v: Version) -> str:
    """The scope text the applicability agent reads: the scope paragraph with its children; for regulations that state it
    in an unnumbered introduction (R19, R38) or under "0." (R6, R123) the first text that says what the regulation applies to."""
    provs = [p for p in provisions(v.regulation, v.version_label) if not p.paragraph.startswith("Annex")]
    for heading in SCOPE_HEADINGS:
        for i, p in enumerate(provs):
            if not p.rationale and heading.match(p.lines[0]):
                block = [p] + [q for q in provs[i + 1:i + 9] if q.number and q.number.startswith(p.number + ".")]
                return "\n".join(q.text for q in block)[:3000]
    for p in provs[:80]:
        text = BANNER.sub("", p.text, count=1)  # "UN R7 (version 3.0.0) / Consolidated text ... / Role in the hackathon: base version."
        hit = APPLIES_TO.search(text)
        if hit and (not p.rationale or p.paragraph == "Introduction"):
            return text[max(0, hit.start() - 150):hit.start() + 2500].lstrip()  # the passage, not the file banner before it
    first = next((p for p in provs if not p.rationale), None)
    return (first.text if first else "")[:3000]


@lru_cache(maxsize=1)
def cards() -> dict[str, Card]:
    out = {}
    for v in base_versions():
        out[v.regulation] = Card(v.regulation, v.title, v.version_label, _scope(v), supersedes(page_text(v)))
    return out
