"""Market layer of a run (design spec section 9.3). Reads the main result; never changes it."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.agents.grounding_verifier import build_grounding_prompt, create_grounding_verifier
from app.agents.synergy_advisor import build_synergy_prompt, create_synergy_advisor
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.corpus.store import CorpusStore
from app.gates.advice_gate import SynergyInput, advice_claims, advice_gate
from app.markets.math import CoreExtras, MarketRequirement, core_and_extras, fix_ranking, market_sets, verdicts
from app.markets.profiles import BUILTIN_DIR, load_market_profiles
from app.models import MarketProfile, MarketVerdict, ProductProfile, Requirement, ShipPlan
from app.pipeline.calls import AgentCall
from app.pipeline.loop import LoopSpec, run_verified

TOP = 30


@dataclass
class MarketsResult:
    sets: dict[str, list[MarketRequirement]]
    core_extras: CoreExtras
    verdicts: list[MarketVerdict]
    ship_plan: ShipPlan | None
    profiles: list[MarketProfile]
    fix_ranking: list

    def as_dict(self) -> dict:
        return {"markets": {"profiles": [p.model_dump() for p in self.profiles],
                            "sets": {m: [asdict(x) for x in items] for m, items in self.sets.items()},
                            "core_extras": asdict(self.core_extras), "verdicts": [v.model_dump() for v in self.verdicts],
                            "fix_ranking": [asdict(f) for f in self.fix_ranking]},
                "ship_plan": self.ship_plan.model_dump() if self.ship_plan else None}


def available_profiles(settings: Settings, regulations: list[str]) -> list[MarketProfile]:
    return load_market_profiles([BUILTIN_DIR, settings.markets_dir], regulations)


async def run_markets(reqs: list[Requirement], market_ids: list[str], profiles: list[MarketProfile],
                      store: CorpusStore, settings: Settings, profile: ProductProfile | None, call: AgentCall,
                      ledger: Ledger | None, changed_texts: dict[str, str] | None = None) -> MarketsResult:
    chosen = [p for p in profiles if p.market_id in market_ids]
    if not chosen:
        return MarketsResult(sets={}, core_extras=CoreExtras([], {}, []), verdicts=[], ship_plan=None, profiles=[],
                             fix_ranking=[])
    sets = market_sets(reqs, chosen, store, changed_texts)
    vs = verdicts(sets, chosen, reqs)
    ranking = fix_ranking(vs)
    by_id = {r.id: r for r in reqs}
    top = [by_id[f.requirement_id] for f in ranking[:TOP] if f.requirement_id in by_id]
    inp = SynergyInput(sets=sets, core_extras=core_and_extras(sets), verdicts=vs, fix_ranking=ranking,
                       top_requirements=top, profiles=chosen,
                       profile_summary={"product_type": profile.product_type if profile else "",
                                        "parts": [p.name for p in profile.parts] if profile else []})
    plan = None
    if reqs:
        loop = LoopSpec(name="ship_plan", producer=create_synergy_advisor(settings), output_schema=ShipPlan,
                        build_prompt=build_synergy_prompt, gate=advice_gate, verifier=create_grounding_verifier(settings),
                        build_review_prompt=lambda i, p: build_grounding_prompt(advice_claims(i, p)),
                        max_retries=settings.max_retries)
        plan = (await run_verified(loop, inp, call, ledger)).output
    return MarketsResult(sets=sets, core_extras=inp.core_extras, verdicts=vs, ship_plan=plan, profiles=chosen,
                         fix_ranking=ranking)


async def run_markets_step(rc: Any) -> None:
    state = rc.state
    if not state.markets:
        state.markets_result = None
        return
    regulations = sorted({v.regulation for v in rc.deps.versions})
    profiles = available_profiles(rc.settings, regulations)
    unknown = sorted(set(state.markets) - {p.market_id for p in profiles})
    if unknown:
        state.give_ups.append(f"markets: unknown market ids {', '.join(unknown)}")
    result = await run_markets(state.requirements, state.markets, profiles, rc.deps.store, rc.settings, state.profile,
                               rc.call, rc.ledger)
    state.markets_result = result.as_dict()
