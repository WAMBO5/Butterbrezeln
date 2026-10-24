"""`report.md` of a run: label, funnel, decisions, give-ups, validation, score, cost."""

from __future__ import annotations

from app.compliance.provenance import UNREVIEWED_LABEL
from app.gates.scope_gate import KEPT
from app.pipeline.state import RunState


def _table(rows: list[list[str]], header: list[str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def render_report(state: RunState, models: dict[str, str]) -> str:
    out: list[str] = []
    if state.mode == "benchmark" or not state.human_actions:
        out.append(UNREVIEWED_LABEL)
    out += ["", f"# Certivity run `{state.run_id}`", "",
            f"- Case: `{state.case_id}` · mode: {state.mode} · status: {state.status if state.status != 'running' else 'done'}",
            f"- Started {state.started_at} · finished {state.finished_at}"]
    if state.partial:
        out.append("- **Partial run: budget reached.** Model calls stopped at the budget; later items are flagged.")
    if state.stopped:
        out.append("- **Stopped by reviewer.**")
    if state.error:
        out.append(f"- **Error:** {state.error}")
    c = state.stage_counts
    out += ["", "## Funnel", "",
            _table([[str(c.get(k, 0)) for k in ("regulations", "kept_regulations", "sections", "candidate_provisions",
                                                 "obligations", "requirements")]],
                   ["regulations in index", "kept", "sections", "candidate provisions", "obligations",
                    "requirements"])]
    if state.plan:
        kept = [d for d in state.plan.decisions if d.state in KEPT]
        per_reg: dict[str, int] = {}
        for r in state.requirements:
            per_reg[r.source.regulation] = per_reg.get(r.source.regulation, 0) + 1
        out += ["", "## Regulations kept", ""]
        out += [f"- **{d.regulation}** {d.version_label} — {d.state} via {d.path}; "
                f"{per_reg.get(d.regulation, 0)} requirements. {d.reason}" for d in kept] or ["- none"]
        out += ["", f"{len(state.plan.decisions) - len(kept)} regulations were excluded (reasons in scope_plan.json)."]
    if state.requirements:
        states = {s: sum(1 for r in state.requirements if r.state == s) for s in ("applicable", "uncertain")}
        evidence = {s: sum(1 for r in state.requirements if r.evidence_status == s)
                    for s in ("met", "not_met", "evidence_needed")}
        out += ["", "## Requirements", "",
                f"- {len(state.requirements)} requirements: {states['applicable']} applicable, "
                f"{states['uncertain']} uncertain.",
                f"- Evidence: {evidence['met']} met, {evidence['not_met']} not met, "
                f"{evidence['evidence_needed']} evidence needed."]
    out += ["", "## Give-ups and dropped items", ""]
    out += [f"- {g}" for g in state.give_ups] or ["- none"]
    if state.output_issues:
        out.append(f"- Output gate dropped {len(state.output_issues)} requirements (citation or lineage).")
    out += ["", "## Validation", ""]
    out.append("- `tools/validate.py`: no problems." if not state.validation_problems else
               "- `tools/validate.py` problems:\n" + "\n".join(f"  - {p}" for p in state.validation_problems))
    if state.score:
        rows = [[level.split("_")[0], f"{s['precision']:.3f}", f"{s['recall']:.3f}", f"{s['f1']:.3f}",
                 f"{s['n_submitted']} / {s['n_expected']} / {s['n_matched']}"]
                for level, s in state.score.items()]
        out += ["", "## Score against expected.json (offline: regulation and page level)", "",
                _table(rows, ["level", "precision", "recall", "F1", "cited / expected / matched"])]
    if state.missing_texts:
        out += ["", "## Missing regulation texts", "",
                "These versions have no text file; the run continued without them:", ""]
        out += [f"- {m}" for m in state.missing_texts]
    cost = state.cost or {}
    per_agent = cost.get("per_agent", {})
    out += ["", "## Cost per agent", ""]
    if per_agent:
        rows = [[name, row.get("model", ""), str(row.get("calls", 0)), str(row.get("input", 0)),
                 str(row.get("cache_read", 0)), str(row.get("output", 0)), f"${row.get('cost_usd', 0):.4f}"]
                for name, row in sorted(per_agent.items())]
        out.append(_table(rows, ["agent", "model", "calls", "input", "cache read", "output", "cost"]))
    out.append(f"\nTotal: ${cost.get('spent_usd', 0):.4f} of ${cost.get('max_cost_usd', 0):.2f} budget.")
    return "\n".join(out) + "\n"
