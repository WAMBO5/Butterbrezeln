"""Version alignment (`version_delta`, design spec section 7): provisions of two versions paired by
text similarity, first near the same paragraph number, then anywhere for renumbered ones; each
marked unchanged, modified, added or removed."""

from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from app.corpus.parser import normalize, paragraph_key
from app.corpus.store import CorpusStore
from app.models import Provision

RENUMBERED = 0.6
SAME_NUMBER = 0.05  # similarity bonus of the provision with the same number: it wins near ties
MOVED_WORDS = 8  # identical text far away is a candidate only when it is unique and this long
LABEL_RE = re.compile(r"^(.*?)(\d+(?:\.\d+)*)$")


@dataclass
class ProvisionChange:
    paragraph: str
    status: Literal["unchanged", "modified", "added", "removed"]
    old: Provision | None
    new: Provision | None


def _pair(old: Provision, new: Provision) -> ProvisionChange:
    same = normalize(old.text) == normalize(new.text)
    return ProvisionChange(paragraph=old.paragraph, status="unchanged" if same else "modified", old=old, new=new)


def _parent(label: str) -> str | None:
    """The label one level up: "5.3.7" for "5.3.7.2", "Annex 3 " for "Annex 3 2", "" for "5"."""
    m = LABEL_RE.match(label)
    return m.group(1) + m.group(2).rpartition(".")[0] if m else None


def _lineage(label: str) -> list[str]:
    """The label and every label above it, up to the top of its annex or of the main text."""
    out = [label]
    while out[-1][-1:].isdigit():
        out.append(_parent(out[-1]))
    return out


def _similarity(a: list[str], b: list[str], floor: float = 0.0) -> float:
    """Word-level similarity of two texts; 0 when it is surely below `floor`."""
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return 0.0 if m.real_quick_ratio() < floor or m.quick_ratio() < floor else m.ratio()


def align_provisions(old: list[Provision], new: list[Provision]) -> list[ProvisionChange]:
    """The most similar pairs first among the candidates near each old provision (the new one with its
    number, its parent paragraph and everything under that, identical text anywhere); the one with its
    number wins near ties and is taken when nothing better is left. The rest pair with the most similar
    anywhere."""
    old_words = [normalize(p.text).split() for p in old]
    new_words = [normalize(q.text).split() for q in new]
    same: dict[str | None, int] = {}
    near: dict[str, list[int]] = {}
    by_text: dict[str, list[int]] = {}
    for j, q in enumerate(new):
        same.setdefault(paragraph_key(q.paragraph), j)
        for label in _lineage(q.paragraph):
            near.setdefault(label, []).append(j)
        by_text.setdefault(" ".join(new_words[j]), []).append(j)
    old_texts = Counter(" ".join(w) for w in old_words)
    edges: list[tuple[float, int, int, int]] = []
    for i, p in enumerate(old):
        s, text, parent = same.get(paragraph_key(p.paragraph)), " ".join(old_words[i]), _parent(p.paragraph)
        moved = by_text.get(text, [])
        moved = moved if len(moved) == 1 and old_texts[text] == 1 and len(old_words[i]) >= MOVED_WORDS else []
        for j in sorted({*(near.get(parent, []) if parent is not None else []), *moved} - {s}):
            score = _similarity(old_words[i], new_words[j], RENUMBERED)
            if score >= RENUMBERED:
                edges.append((-score, 1, i, j))
        if s is not None:
            edges.append((-_similarity(old_words[i], new_words[s]) - SAME_NUMBER, 0, i, s))
    match: dict[int, int] = {}
    taken: set[int] = set()
    for _, _, i, j in sorted(edges):
        if i not in match and j not in taken:
            match[i] = j
            taken.add(j)
    free = [j for j in range(len(new)) if j not in taken]
    for i in range(len(old)):
        if i not in match and free:
            scores = [_similarity(old_words[i], new_words[j], RENUMBERED) for j in free]
            best = max(range(len(free)), key=scores.__getitem__)
            if scores[best] >= RENUMBERED:
                match[i] = free.pop(best)
    changes = [_pair(p, new[match[i]]) if i in match else
               ProvisionChange(paragraph=p.paragraph, status="removed", old=p, new=None) for i, p in enumerate(old)]
    return changes + [ProvisionChange(paragraph=new[j].paragraph, status="added", old=None, new=new[j]) for j in free]


def align_versions(store: CorpusStore, regulation: str, old_label: str, new_label: str) -> list[ProvisionChange]:
    return align_provisions(store.provisions(regulation, old_label), store.provisions(regulation, new_label))
