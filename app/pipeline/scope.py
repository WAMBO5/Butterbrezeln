"""Scope narrowing loop: `scope_narrower` (tools) → scope gate → safety net → `recall_auditor`, run as
several independent samples that code merges by vote (`app/matching/scope_vote.py`)."""

from __future__ import annotations

import asyncio

from app.agents.recall_auditor import build_audit_prompt, create_recall_auditor
from app.agents.scope_narrower import build_scope_prompt, create_scope_narrower
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.gates.scope_gate import ScopeContext, scope_gate
from app.matching.safety_net import SafetyHit, safety_net
from app.matching.scope_vote import merge_plans
from app.models import RegulationCard, RegulationVersion, ScopePlan
from app.pipeline.calls import AgentCall
from app.pipeline.loop import LoopResult, LoopSpec, run_verified
from app.tools.corpus_tools import bind_store

SAFETY_TOP_K = 5


def placeholder_card(v: RegulationVersion) -> RegulationCard:
    """A card for a regulation without one (no text yet, or its card failed): title only."""
    return RegulationCard(regulation=v.regulation, version_label=v.version_label, title=v.title,
                          regulation_type="other", devices_in_scope=[], vehicle_categories=[], functions_covered=[],
                          triggers=[], consolidates=[], device_sections=[],
                          evidence=["no card: decide from the title and the tools"])


async def narrow_scope(ctx: ScopeContext, settings: Settings, call: AgentCall,
                       ledger: Ledger | None) -> tuple[LoopResult[ScopePlan], list[SafetyHit]]:
    bind_store(ctx.store)
    loop = LoopSpec(
        name="scope_plan", producer=create_scope_narrower(settings, ctx.cards), output_schema=ScopePlan,
        build_prompt=lambda c, feedback: build_scope_prompt(c.profile, feedback), gate=scope_gate,
        verifier=create_recall_auditor(settings),
        build_review_prompt=lambda c, plan: build_audit_prompt(c, plan, safety_net(c.store, c.profile, plan,
                                                                                   SAFETY_TOP_K)),
        max_retries=settings.max_retries,
    )
    result = await run_verified(loop, ctx, call, ledger)
    hits = safety_net(ctx.store, ctx.profile, result.output, SAFETY_TOP_K) if result.output else []
    return result, hits


async def narrow_scope_voted(ctx: ScopeContext, settings: Settings, call: AgentCall,
                             ledger: Ledger | None) -> tuple[ScopePlan | None, dict, list[SafetyHit]]:
    """`settings.scope_samples` independent scope loops, merged by vote: the plan, a loop summary with
    each sample's summary and the votes, and the safety-net hits for the merged plan."""
    samples = await asyncio.gather(*(narrow_scope(ctx, settings, call, ledger) for _ in range(settings.scope_samples)))
    results = [r for r, _ in samples]
    plans = [r.output for r in results if r.output is not None]
    plan, votes = merge_plans(plans) if plans else (None, {})
    if ledger is not None and len(plans) > 1:
        ledger.append("gate", "gate:scope_vote", None, None, {"samples": len(plans), "votes": votes})
    unresolved = [r for r in results if not r.resolved]
    summary = {"resolved": len(unresolved) < len(results), "attempts": sum(len(r.attempts) for r in results),
               "open_issues": [i.model_dump() for r in unresolved for i in r.open_issues][:20],
               "samples": [r.summary() for r in results], "votes": votes}
    hits = safety_net(ctx.store, ctx.profile, plan, SAFETY_TOP_K) if plan else []
    return plan, summary, hits
