"""Scope narrowing loop: `scope_narrower` (tools) → scope gate → safety net → `recall_auditor`."""

from __future__ import annotations

from app.agents.recall_auditor import build_audit_prompt, create_recall_auditor
from app.agents.scope_narrower import build_scope_prompt, create_scope_narrower
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.gates.scope_gate import ScopeContext, scope_gate
from app.matching.safety_net import SafetyHit, safety_net
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
