"""Deterministic verifier and export. Fail closed: a row that does not check out is dropped and logged, never patched."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz

from pipeline import config
from pipeline.catalog.corpus import find_version, page_count
from pipeline.catalog.normalise import content_words, is_subsequence, normalise, number_sequence, numbers
from pipeline.catalog.parse import Provision

FUZZY_QUOTE_MIN = 96   # partial match score accepted when the exact normalised substring fails (extraction artefacts)
MIN_QUOTE = 20         # characters of quote (all fragments together); a generic 8-character quote proves nothing
MIN_FRAGMENT = 10      # characters per fragment of a quote written with an ellipsis
MIN_TEXT_OVERLAP = 0.45  # share of the draft's content words that must occur in the evidence (gold rows: at least 0.5)
ELLIPSIS = re.compile(r"\s*(?:\[\s*\.\.\.\s*\]|\.\.\.|…)\s*")


@dataclass
class Row:
    text: str
    regulation: str
    version: str
    page: int
    paragraph: str
    provision_id: str
    quote: str
    quote_match: str  # "exact" or "fuzzy"


def _related_labels(p: Provision) -> set[str]:
    """Numbers of the provision's children and parents, plus its section siblings in the main body: a requirement may
    name "paragraph 5.1.4." without that number appearing in the cited text. Annex provisions get no sibling allowance,
    because annex paragraph numbers are small integers that would let invented values through."""
    from pipeline.catalog.corpus import provisions as all_provisions

    out: set[str] = set()
    num = p.number or ""
    parts = num.split(".") if num else []
    parents = {".".join(parts[:i]) for i in range(1, len(parts))}
    in_annex = p.paragraph.startswith("Annex")
    parent = ".".join(parts[:-1])
    for q in all_provisions(p.regulation, p.version_label):
        if not q.number:
            continue
        if in_annex:  # only siblings under the same parent paragraph ("1.2.1" from "1.2.2"), in the same annex
            sibling = bool(parent) and q.section == p.section and q.number.startswith(parent + ".")
        else:
            sibling = q.section == p.section
        if sibling or (num and q.number.startswith(num + ".")) or q.number in parents:
            out.add(q.number)
    return out


def _find_fragment(fragment: str, ev_norm: str, start: int) -> tuple[str, int] | None:
    """("exact" | "fuzzy", end offset) of `fragment` in ev_norm at or after `start`, else None.

    A fuzzy match (extraction artefacts only) must not change a number: the fragment's numbers, in order, must all be
    in the aligned evidence text."""
    i = ev_norm.find(fragment, start)
    if i >= 0:
        return "exact", i + len(fragment)
    window = ev_norm[start:]
    al = fuzz.partial_ratio_alignment(fragment, window)
    if not al or al.score < FUZZY_QUOTE_MIN:
        return None
    lo, hi = al.dest_start, al.dest_end
    while lo > 0 and not window[lo - 1].isspace():  # the window may cut a number or word at its edge
        lo -= 1
    while hi < len(window) and not window[hi].isspace():
        hi += 1
    if not is_subsequence(number_sequence(fragment), number_sequence(window[lo:hi])):
        return None
    return "fuzzy", start + hi


def _match_quote(quote_norm: str, ev_norm: str) -> tuple[str | None, str]:
    """(match kind, drop reason). The quote may be several fragments joined by "...", found in order."""
    fragments = [f for f in ELLIPSIS.split(quote_norm) if f.strip()]
    if len(quote_norm) < MIN_QUOTE or any(len(f) < MIN_FRAGMENT for f in fragments):
        return None, "quote too short"
    kind, pos = "exact", 0
    for fragment in fragments:
        found = _find_fragment(fragment.strip(), ev_norm, pos)
        if found is None:
            return None, "quote not in cited text"
        kind = "fuzzy" if found[0] == "fuzzy" else kind
        pos = found[1]
    return kind, ""


def verify(drafts: list[dict], provisions: dict[str, Provision], xrefs: dict[str, str]) -> tuple[list[Row], Counter, list[dict]]:
    rows: list[Row] = []
    drops: Counter = Counter()
    dropped: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()

    def drop(reason: str, d: dict) -> None:
        drops[reason] += 1
        dropped.append({**d, "drop_reason": reason})

    for d in drafts:
        p = provisions.get(d["provision_id"])
        text = " ".join((d.get("text") or "").split())
        if p is None:
            drop("unknown provision", d); continue
        v = find_version(p.regulation, p.version_label)
        if v is None or v.role != "base":
            drop("not a base version in index.json", d); continue
        if not text or len(text) > 2000:
            drop("empty or too long text", d); continue
        evidence = p.text + "\n" + xrefs.get(p.provision_id, "")
        match, reason = _match_quote(normalise(d.get("quote") or ""), normalise(evidence))
        if match is None:
            drop(reason, d); continue
        words = content_words(text)
        if len(words) >= 3 and len(words & content_words(evidence + " " + " ".join(p.heading_path))) / len(words) < MIN_TEXT_OVERLAP:
            drop("text not supported by the cited text", d); continue
        allowed = numbers(evidence + " " + " ".join(p.heading_path), evidence=True) | _related_labels(p)
        # A number may be written joined ("1 200") or split; accept the draft if either reading is fully supported.
        extra = numbers(text) - allowed
        if extra and not (numbers(text, join=False) - allowed):
            extra = set()
        if extra:
            drop("number not in evidence", {**d, "numbers": sorted(extra)}); continue
        # Cite the provision's first page, as the gold file does (its multi-page provisions all cite their first page).
        if not 1 <= p.page <= page_count(v):
            drop("page outside PDF", d); continue
        key = (p.regulation, p.version_label, p.paragraph, normalise(text))
        if key in seen:
            drop("duplicate", d); continue
        seen.add(key)
        rows.append(Row(text, p.regulation, p.version_label, p.page, p.paragraph, p.provision_id, d.get("quote", ""), match))
    return rows, drops, dropped


def _load_tool(name: str):
    path = config.HACKATHON_DIR / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"hackathon_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _validate_module():
    return _load_tool("validate")


def submission(rows: list[Row], case_id: str, team_id: str) -> dict:
    return {"team_id": team_id, "case_id": case_id, "requirements": [
        {"id": f"R-{i:03d}", "text": r.text,
         "source": {"regulation": r.regulation, "version": r.version, "page": r.page, "paragraph": r.paragraph}}
        for i, r in enumerate(rows, start=1)]}


def validate(path: Path) -> list[str]:
    """Run the organizer's validate.py exactly as the platform does."""
    mod = _validate_module()
    data = json.loads(path.read_text(encoding="utf-8"))
    index = json.loads(config.INDEX_JSON.read_text(encoding="utf-8"))
    return [str(p) for p in mod.validate(data, index=index)]


def score(path: Path, expected: Path) -> dict | None:
    if not expected.is_file():
        return None
    mod = _load_tool("score_local")
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    return mod.score(load(path), load(expected))
