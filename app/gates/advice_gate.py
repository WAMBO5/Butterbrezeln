"""Code gate for the ship plan (design spec section 6.7) and the claims `grounding_verifier` checks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.markets.math import CoreExtras, FixRank, MarketRequirement, markets_unlocked
from app.models import Claim, Issue, MarketProfile, MarketVerdict, Requirement, ShipPlan

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class SynergyInput:
    sets: dict[str, list[MarketRequirement]]
    core_extras: CoreExtras
    verdicts: list[MarketVerdict]
    fix_ranking: list[FixRank]
    top_requirements: list[Requirement]
    profile_summary: dict
    profiles: list[MarketProfile]


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def _texts(inp: SynergyInput) -> dict[str, str]:
    texts = {x.requirement_id: x.text for items in inp.sets.values() for x in items}
    texts.update({r.id: r.text for r in inp.top_requirements})
    return texts


def advice_gate(inp: SynergyInput, plan: ShipPlan) -> list[Issue]:
    texts = _texts(inp)
    issues: list[Issue] = []
    for n, action in enumerate(plan.actions, start=1):
        target = f"action {n}"
        unknown = [rid for rid in action.requirement_ids if rid not in texts]
        if unknown or not action.requirement_ids:
            issues.append(_issue("unknown_id", target, f"requirement ids must come from the payload: {unknown or 'none given'}"))
            continue
        expected = markets_unlocked(action.requirement_ids, inp.verdicts)
        if sorted(action.markets_unlocked) != expected:
            issues.append(_issue("markets_unlocked", target, f"these requirements unlock exactly {expected}, "
                                                             f"not {sorted(action.markets_unlocked)}"))
        cited = " ".join(texts[rid] for rid in action.requirement_ids)
        invented = [num for num in NUMBER_RE.findall(action.rationale) if num not in NUMBER_RE.findall(cited)]
        if invented:
            issues.append(_issue("invented_number", target, f"the rationale uses numbers not in the cited requirements: "
                                                            f"{', '.join(invented)}; remove them or cite their source"))
    return issues


def advice_claims(inp: SynergyInput, plan: ShipPlan) -> list[Claim]:
    texts = _texts(inp)
    return [Claim(claim_id=f"action:{n}", text=f"{a.title}: {a.rationale}",
                  cited_text="\n".join(f"[{rid}] {texts.get(rid, '')}" for rid in a.requirement_ids)[:4000])
            for n, a in enumerate(plan.actions, start=1)]
