"""`synergy_advisor`: the smallest set of changes, tests and documents that opens the most markets
(design spec section 6.7). It sees results computed by code, never the regulation text."""

from __future__ import annotations

import json

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.config.settings import Settings
from app.gates.advice_gate import SynergyInput
from app.models import Issue, ShipPlan

INSTRUCTION = """\
You plan how to make a product shippable in as many of the selected markets as possible. Code has
already computed each market's requirement set, the shared core and the extras, a verdict per market
and a fix ranking (each blocking or unproven requirement and the markets it holds back). You do not
decide which requirements apply.

Return a ship plan:
- envelope_summary: two or three sentences on what designing to the whole envelope means here.
- actions, most valuable first: a design change, a test that produces evidence, or a document. Each
  names the requirement ids it addresses and markets_unlocked: the markets whose every blocking and
  unproven requirement is covered by those ids (code checks this, so list exactly those).
- synergies: one test or change that serves several markets at once.
- caveats: illustrative market data, markets marked not covered because they rely on rules outside
  the corpus, and evidence judged from the spec only.
Use no number in a rationale that is not in the cited requirement texts. If the payload lists
feedback, fix every issue.
"""


def create_synergy_advisor(settings: Settings) -> AgentSpec:
    return make_agent(name="synergy_advisor", description="Proposes changes and tests that open the most markets",
                      instruction=INSTRUCTION, output_schema=ShipPlan, tier="judgment", effort="medium",
                      settings=settings)


def build_synergy_prompt(inp: SynergyInput, feedback: list[Issue]) -> str:
    names = {p.market_id: p.name for p in inp.profiles}
    markets = "\n".join(
        f"{p.market_id} ({p.name}{', illustrative' if p.illustrative else ''}): "
        f"{sum(1 for r in p.rules if r.status != 'not_applied')} regulations applied; "
        f"not applied: {[r.regulation for r in p.rules if r.status == 'not_applied'] or 'none'}; "
        f"on latest versions: {[r.regulation for r in p.rules if r.version_role == 'latest'] or 'none'}; "
        f"rules outside the corpus: {len(p.outside_corpus)}" for p in inp.profiles)
    ranking = {f.requirement_id: f.markets_held_back for f in inp.fix_ranking}
    top = "\n".join(f"[{r.id}] {r.source.regulation} p.{r.source.page} §{r.source.paragraph} — "
                    f"{r.evidence_status}; holds back {ranking.get(r.id, [])}: {r.text}" for r in inp.top_requirements)
    return render_prompt(
        task="Write the ship plan for the selected markets.",
        context=[("Product", json.dumps(inp.profile_summary, ensure_ascii=False)), ("Markets", markets),
                 ("Shared core and extras", f"core: {len(inp.core_extras.core)} requirements; " + "; ".join(
                     f"{names.get(m, m)} extras: {len(v)}" for m, v in inp.core_extras.extras.items())),
                 ("Requirements that hold markets back (top of the fix ranking)", top or "(none)")],
        untrusted=[],
        payload={"markets": [p.market_id for p in inp.profiles],
                 "top_requirement_ids": [r.id for r in inp.top_requirements],
                 "verdicts": [v.model_dump() for v in inp.verdicts],
                 "feedback": [i.model_dump() for i in feedback]},
    )
