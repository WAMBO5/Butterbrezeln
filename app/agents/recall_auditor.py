"""`recall_auditor`: which excluded regulation or section could still apply? (spec section 6.9)"""

from __future__ import annotations

import json

from app.agents.factory import AgentSpec, make_agent
from app.agents.prompting import render_prompt
from app.agents.scope_narrower import render_cards
from app.config.settings import Settings
from app.gates.scope_gate import KEPT, ScopeContext
from app.matching.safety_net import SafetyHit
from app.models import Review, ScopePlan

INSTRUCTION = """\
You audit a scope plan for recall. You see the product profile, the plan, the cards of every
regulation the plan excluded, full-text search hits computed by code for the product's parts
(regulations the plan excluded that still rank high come first), and the tables of contents of the
regulations the plan kept.

Report only well-founded problems:
- "missed_regulation": an excluded regulation that applies to a part as its device, through the
  installation of its function, or through a property of the part that triggers it.
- "missed_section": a kept regulation whose kept sections leave out a section that binds a part, such
  as its markings section, general specifications, or an annex test procedure that a kept section uses.
- "wrong_inclusion": a kept regulation that a kept regulation consolidates, or that only covers vehicle
  categories the product is not for.

Each issue: target_id the regulation ("UN R10") or section id, reason, evidence (card fields or
provision ids), proposed (the state or section ids you propose). Keyword overlap alone is not a
reason. Return verdict "pass" with no issues when nothing is missing.
"""


def create_recall_auditor(settings: Settings) -> AgentSpec:
    return make_agent(name="recall_auditor", description="Challenges what the scope plan excluded",
                      instruction=INSTRUCTION, output_schema=Review, tier="review", effort="high", settings=settings)


def build_audit_prompt(ctx: ScopeContext, plan: ScopePlan, hits: list[SafetyHit]) -> str:
    excluded = {d.regulation for d in plan.decisions if d.state == "not_applicable"}
    kept = [d for d in plan.decisions if d.state in KEPT]
    decisions = "\n".join(
        f"{d.regulation} {d.version_label}: {d.state} ({d.path}) parts={d.part_ids} "
        f"sections={[{'part': s.part_id, 'ids': s.section_ids} for s in d.sections]} — {d.reason}"
        for d in sorted(plan.decisions, key=lambda d: d.regulation))
    hit_lines = "\n".join(f"{'EXCLUDED ' if h.excluded else ''}{h.regulation} rank {h.best_rank} for: {h.query}"
                          for h in hits) or "(none)"
    tocs = []
    for d in kept:
        toc = ctx.store.toc(d.regulation, d.version_label, 2)
        tocs.append(f"## {d.regulation} {d.version_label}\n" + "\n".join(
            f"{e.provision_id} | p.{e.page} | {e.kind} | {e.heading[:80]}" for e in toc if e.kind != "form"))
    return render_prompt(
        task="Audit this scope plan for missed regulations, missed sections and wrong inclusions.",
        context=[("Product profile", json.dumps(ctx.profile.model_dump(), indent=1, ensure_ascii=False)),
                 ("Scope plan", decisions),
                 ("Cards of excluded regulations", render_cards([c for c in ctx.cards if c.regulation in excluded])),
                 ("Search hits (code-run, per part)", hit_lines),
                 ("Tables of contents of kept regulations (depth 2)", "\n\n".join(tocs) or "(none)")],
        untrusted=[],
        payload={"kept": sorted(d.regulation for d in kept), "excluded": sorted(excluded)},
    )
