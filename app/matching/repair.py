"""One repair round after `output_auditor` (design spec section 6.9): duplicates dropped, merged
or unclear requirements sent back to extraction, label format fixed in code."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models import Requirement, Review


@dataclass
class RepairPlan:
    kept: list[Requirement]
    reextract: list[str] = field(default_factory=list)  # provision ids
    dropped: list[str] = field(default_factory=list)  # requirement ids


def fix_label(label: str | None) -> str | None:
    if label is None:
        return None
    text = re.sub(r"[,;:]", " ", label)
    text = re.sub(r"(?<![0-9A-Za-z])\.|\.(?![0-9A-Za-z])", " ", text)
    text = re.sub(r"^(paragraphs?|para|§)\s*", "", " ".join(text.split()), flags=re.I)
    return text or None


def _number(rid: str) -> int:
    digits = re.sub(r"\D", "", rid)
    return int(digits) if digits else 0


def apply_output_review(reqs: list[Requirement], review: Review) -> RepairPlan:
    by_id = {r.id: r for r in reqs}
    drop: set[str] = set()
    redo: set[str] = set()
    fix: set[str] = set()
    for issue in review.issues:
        if issue.target_id not in by_id:
            continue
        if issue.type == "duplicate":
            # the same wording in two regulations is two requirements: each regulation must be met
            regulation = by_id[issue.target_id].source.regulation
            partners = [e for e in issue.evidence if e in by_id and e != issue.target_id
                        and by_id[e].source.regulation == regulation]
            if partners:
                drop.add(max([issue.target_id, *partners], key=_number))
        elif issue.type in ("merged", "unclear_subject"):
            redo.add(issue.target_id)
        elif issue.type == "format":
            fix.add(issue.target_id)
    reextract: list[str] = []
    kept: list[Requirement] = []
    for r in reqs:
        if r.id in drop:
            continue
        if r.id in redo:
            for oid in r.obligation_ids:
                pid = oid.rsplit("/", 1)[0]
                if pid not in reextract:
                    reextract.append(pid)
            continue
        if r.id in fix:
            r = r.model_copy(update={"source": r.source.model_copy(update={"paragraph": fix_label(r.source.paragraph)})})
        kept.append(r)
    return RepairPlan(kept=kept, reextract=reextract, dropped=sorted(drop, key=_number))
