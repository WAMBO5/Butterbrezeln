"""Market math (design spec section 9.3): requirement set per market, shared core and extras,
verdicts, and the fix ranking. Code only; it reads the main result and never changes it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.corpus.parser import paragraph_key
from app.corpus.store import CorpusStore
from app.markets.delta import ProvisionChange, align_versions
from app.models import MarketProfile, MarketVerdict, Requirement


@dataclass
class MarketRequirement:
    requirement_id: str
    regulation: str
    version_label: str
    page: int
    paragraph: str
    text: str
    change: Literal["same", "changed_in_latest"]


@dataclass
class CoreExtras:
    core: list[str]
    extras: dict[str, list[str]]
    envelope: list[str]


@dataclass
class FixRank:
    requirement_id: str
    markets_held_back: list[str] = field(default_factory=list)


def _rid_key(rid: str) -> tuple:
    digits = "".join(ch for ch in rid if ch.isdigit())
    return (int(digits) if digits else 0, rid)


def market_sets(reqs: list[Requirement], profiles: list[MarketProfile], store: CorpusStore,
                changed_texts: dict[str, str] | None = None) -> dict[str, list[MarketRequirement]]:
    """Requirements each market asks for. On a `latest` rule an unchanged requirement is re-cited to the
    latest version, a modified one is marked `changed_in_latest` (with the change analyst's new text when
    given), and a removed one is dropped."""
    alignments: dict[str, dict[str, ProvisionChange]] = {}

    def latest_change(regulation: str, base: str, paragraph: str) -> tuple[str, ProvisionChange] | None:
        latest = next((v for v in store.versions() if v.regulation == regulation and v.role == "latest"), None)
        if latest is None or not store.has_text(regulation, latest.version_label):
            return None
        if regulation not in alignments:
            alignments[regulation] = {paragraph_key(c.paragraph): c
                                      for c in align_versions(store, regulation, base, latest.version_label) if c.old}
        change = alignments[regulation].get(paragraph_key(paragraph))
        return (latest.version_label, change) if change else None

    sets: dict[str, list[MarketRequirement]] = {}
    for profile in profiles:
        rules = {r.regulation: r for r in profile.rules}
        out: list[MarketRequirement] = []
        for r in reqs:
            rule = rules.get(r.source.regulation)
            if rule is None or rule.status == "not_applied":
                continue
            item = MarketRequirement(r.id, r.source.regulation, r.source.version, r.source.page,
                                     r.source.paragraph or "", r.text, "same")
            if rule.version_role == "latest":
                found = latest_change(r.source.regulation, r.source.version, r.source.paragraph or "")
                if found is not None:
                    label, change = found
                    if change.status == "removed":
                        continue
                    item.version_label, item.page = label, change.new.page_start
                    if change.status == "modified":
                        item.change = "changed_in_latest"
                        item.text = (changed_texts or {}).get(r.id, r.text)
            out.append(item)
        sets[profile.market_id] = out
    return sets


def core_and_extras(sets: dict[str, list[MarketRequirement]]) -> CoreExtras:
    ids = {m: {x.requirement_id for x in items} for m, items in sets.items()}
    core = set.intersection(*ids.values()) if ids else set()
    envelope = set.union(*ids.values()) if ids else set()
    return CoreExtras(core=sorted(core, key=_rid_key),
                      extras={m: sorted(v - core, key=_rid_key) for m, v in ids.items()},
                      envelope=sorted(envelope, key=_rid_key))


def verdicts(sets: dict[str, list[MarketRequirement]], profiles: list[MarketProfile],
             reqs: list[Requirement]) -> list[MarketVerdict]:
    by_id = {r.id: r for r in reqs}
    extras = core_and_extras(sets).extras
    out = []
    for profile in profiles:
        status = {r.regulation: r.status for r in profile.rules}
        items = [by_id[x.requirement_id] for x in sets.get(profile.market_id, []) if x.requirement_id in by_id]
        blocking = [r.id for r in items if r.evidence_status == "not_met" and status.get(r.source.regulation) == "mandatory"]
        missing = [r.id for r in items if r.evidence_status != "met" and r.id not in blocking]
        if profile.outside_corpus:
            verdict = "not_covered"
        elif blocking:
            verdict = "blocked"
        elif missing:
            verdict = "evidence_needed"
        else:
            verdict = "ready"
        out.append(MarketVerdict(market_id=profile.market_id, verdict=verdict, blocking=sorted(blocking, key=_rid_key),
                                 missing_evidence=sorted(missing, key=_rid_key),
                                 extras=extras.get(profile.market_id, [])))
    return out


def fix_ranking(vs: list[MarketVerdict]) -> list[FixRank]:
    held: dict[str, list[str]] = {}
    for v in vs:
        for rid in [*v.blocking, *v.missing_evidence]:
            held.setdefault(rid, []).append(v.market_id)
    return sorted((FixRank(rid, markets) for rid, markets in held.items()),
                  key=lambda f: (-len(f.markets_held_back), _rid_key(f.requirement_id)))


def markets_unlocked(ids: list[str], vs: list[MarketVerdict]) -> list[str]:
    """Markets that become ready once every listed requirement is fixed or proven."""
    chosen = set(ids)
    return sorted(v.market_id for v in vs if v.verdict in ("blocked", "evidence_needed")
                  and set(v.blocking) | set(v.missing_evidence) <= chosen)
