"""Version alignment (`version_delta`, design spec section 7): provisions of two versions paired by
paragraph, then by text similarity for renumbered ones; each marked unchanged, modified, added or
removed."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Literal

from app.corpus.parser import normalize, paragraph_key
from app.corpus.store import CorpusStore
from app.models import Provision

RENUMBERED = 0.6


@dataclass
class ProvisionChange:
    paragraph: str
    status: Literal["unchanged", "modified", "added", "removed"]
    old: Provision | None
    new: Provision | None


def _pair(old: Provision, new: Provision) -> ProvisionChange:
    same = normalize(old.text) == normalize(new.text)
    return ProvisionChange(paragraph=old.paragraph, status="unchanged" if same else "modified", old=old, new=new)


def align_provisions(old: list[Provision], new: list[Provision]) -> list[ProvisionChange]:
    new_by_key = {}
    for p in new:
        new_by_key.setdefault(paragraph_key(p.paragraph), p)
    changes: list[ProvisionChange] = []
    used: set[str] = set()
    unmatched_old: list[Provision] = []
    for p in old:
        match = new_by_key.get(paragraph_key(p.paragraph))
        if match is not None and match.provision_id not in used:
            used.add(match.provision_id)
            changes.append(_pair(p, match))
        else:
            unmatched_old.append(p)
    unmatched_new = [p for p in new if p.provision_id not in used]
    for p in unmatched_old:
        text = normalize(p.text)
        best, score = None, 0.0
        for q in unmatched_new:
            ratio = difflib.SequenceMatcher(None, text, normalize(q.text)).ratio()
            if ratio > score:
                best, score = q, ratio
        if best is not None and score >= RENUMBERED:
            unmatched_new.remove(best)
            changes.append(ProvisionChange(paragraph=p.paragraph, status="modified", old=p, new=best)
                           if normalize(best.text) != text else _pair(p, best))
        else:
            changes.append(ProvisionChange(paragraph=p.paragraph, status="removed", old=p, new=None))
    changes += [ProvisionChange(paragraph=q.paragraph, status="added", old=None, new=q) for q in unmatched_new]
    return changes


def align_versions(store: CorpusStore, regulation: str, old_label: str, new_label: str) -> list[ProvisionChange]:
    return align_provisions(store.provisions(regulation, old_label), store.provisions(regulation, new_label))
