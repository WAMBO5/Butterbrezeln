"""Per-stage recall of a run against an expected answer (design spec section 12)."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

from app.compliance.ledger import Ledger
from app.config.settings import Settings, load_settings
from app.corpus.parser import normalize
from app.corpus.store import CorpusStore
from app.gates.scope_gate import KEPT
from app.matching.submission import score_submission
from app.pipeline.state import RunState

SIMILAR = 0.5


@dataclass
class FunnelReport:
    scope_regulations_kept: str
    golden_pages_in_sections: float
    candidate_coverage: float
    final_score: dict
    auditor_added: int
    reviewer_changed: int
    give_ups: int
    cost_usd: float


def funnel_metrics(run_dir: Path, expected_path: Path, store: CorpusStore,
                   settings: Settings | None = None) -> FunnelReport:
    settings = settings or load_settings()
    state = RunState.load(run_dir)
    gold = json.loads(Path(expected_path).read_text(encoding="utf-8"))["requirements"]
    golden_regs = {g["source"]["regulation"] for g in gold}
    kept = {d.regulation for d in state.plan.decisions if d.state in KEPT} if state.plan else set()

    pages: set[tuple[str, int]] = set()
    for c in state.candidates:
        for pid in c["provision_ids"]:
            p = store.get(pid)
            if p is not None:
                pages |= {(p.regulation, n) for n in range(p.page_start, p.page_end + 1)}
    golden_pages = {(g["source"]["regulation"], g["source"]["page"]) for g in gold}

    by_provision: dict[str, list[str]] = {}
    for o in state.obligations.values():
        by_provision.setdefault(o.provision_id, []).append(normalize(o.text))
    covered = 0
    for g in gold:
        s = g["source"]
        p = store.find(s["regulation"], s["version"], s.get("paragraph") or "")
        texts = by_provision.get(p.provision_id, []) if p else []
        if any(difflib.SequenceMatcher(None, t, normalize(g["text"])).ratio() >= SIMILAR for t in texts):
            covered += 1

    submission = json.loads((Path(run_dir) / "submission.json").read_text(encoding="utf-8"))
    ledger = Ledger(Path(run_dir))
    auditor_added = 0
    for r in ledger.records():
        if r.kind == "review" and r.actor == "recall_auditor" and r.meta.get("verdict") == "retry":
            auditor_added += len((ledger.call(r.seq)["output"] or {}).get("issues", []))
    return FunnelReport(
        scope_regulations_kept=f"{len(golden_regs & kept)}/{len(golden_regs)}",
        golden_pages_in_sections=len(golden_pages & pages) / len(golden_pages) if golden_pages else 0.0,
        candidate_coverage=covered / len(gold) if gold else 0.0,
        final_score=score_submission(submission, expected_path, settings),
        auditor_added=auditor_added,
        reviewer_changed=sum(1 for d in state.decisions if "| reviewer:" in d.reason),
        give_ups=len(state.give_ups),
        cost_usd=float((state.cost or {}).get("spent_usd", 0.0)),
    )


def render_funnel(report: FunnelReport) -> str:
    s = report.final_score
    rows = [
        ("golden regulations kept by the scope plan", report.scope_regulations_kept),
        ("golden pages in sections", f"{report.golden_pages_in_sections:.1%}"),
        ("golden requirements with a similar obligation (candidates)", f"{report.candidate_coverage:.1%}"),
        ("regulation level P / R", f"{s['regulation_level']['precision']:.3f} / {s['regulation_level']['recall']:.3f}"),
        ("page level P / R", f"{s['page_level']['precision']:.3f} / {s['page_level']['recall']:.3f}"),
        ("recall auditor issues", str(report.auditor_added)),
        ("decisions changed to uncertain by the match reviewer", str(report.reviewer_changed)),
        ("give-ups", str(report.give_ups)),
        ("cost", f"${report.cost_usd:.4f}"),
    ]
    width = max(len(k) for k, _ in rows)
    return "Funnel\n" + "\n".join(f"  {k.ljust(width)}  {v}" for k, v in rows)
