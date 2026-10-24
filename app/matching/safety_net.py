"""Recall safety net: full-text search for each part, run by code, shown to `recall_auditor`."""

from __future__ import annotations

from dataclasses import dataclass

from app.corpus.store import CorpusStore
from app.models import ProductProfile, ScopePlan


@dataclass(frozen=True)
class SafetyHit:
    regulation: str
    query: str
    best_rank: int
    excluded: bool


def safety_queries(profile: ProductProfile) -> list[str]:
    queries = []
    for part in profile.parts:
        words = [part.name, *part.functions, *part.properties, *part.materials]
        queries.append(" ".join(w for w in words if w))
    return list(dict.fromkeys(q for q in queries if q.strip()))


def safety_net(store: CorpusStore, profile: ProductProfile, plan: ScopePlan, top_k: int) -> list[SafetyHit]:
    excluded = {d.regulation for d in plan.decisions if d.state == "not_applicable"}
    hits: list[SafetyHit] = []
    for query in safety_queries(profile):
        seen: set[str] = set()
        for rank, hit in enumerate(store.search(query, top_k, "base"), start=1):
            if hit.regulation not in seen:
                seen.add(hit.regulation)
                hits.append(SafetyHit(hit.regulation, query, rank, hit.regulation in excluded))
    return sorted(hits, key=lambda h: (not h.excluded, h.best_rank, h.regulation))
