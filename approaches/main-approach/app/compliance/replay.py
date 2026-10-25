"""Offline replay (`certivity verify`, design spec section 14.4): check the ledger chain, then
rebuild requirements, lineage and submission from the recorded snapshot with code only, and diff
them against the files of the run."""

from __future__ import annotations

import json
from pathlib import Path

from app.compliance.ledger import Ledger, canonical, verify_chain
from app.compliance.manifest import file_sha256
from app.compliance.oversight import apply_requirement_pins
from app.config.settings import Settings
from app.corpus.index import load_index
from app.corpus.store import CorpusStore
from app.gates.output_gate import OutputContext, output_gate
from app.matching.assemble import assemble
from app.matching.submission import to_submission
from app.models import MatchDecision, Obligation, ProductProfile, ScopePlan


def _snapshot(ledger: Ledger) -> dict | None:
    for record in reversed(ledger.records()):
        if record.kind == "note" and record.meta.get("snapshot"):
            return ledger.call(record.seq)["output"]
    return None


def _human_actions(ledger: Ledger, fallback: list[dict]) -> list[dict]:
    actions = [ledger.call(r.seq)["input"] for r in ledger.records() if r.kind == "human_action"]
    return [a for a in actions if isinstance(a, dict) and a.get("action")] or fallback


def _same(path: Path, data: object) -> bool:
    if not path.exists():
        return False
    return canonical(json.loads(path.read_text(encoding="utf-8"))) == canonical(data)


def replay(run_dir: Path, store: CorpusStore, settings: Settings) -> list[str]:
    run_dir = Path(run_dir)
    problems = verify_chain(run_dir)
    ledger = Ledger(run_dir)
    snap = _snapshot(ledger)
    if snap is None:
        return problems + ["no assembly snapshot in the ledger: the run did not reach assembly"]
    obligations = {k: Obligation(**v) for k, v in snap["obligations"].items()}
    decisions = [MatchDecision(**d) for d in snap["decisions"]]
    dropped = set(snap["dropped"])
    profile, plan = ProductProfile(**snap["profile"]), ScopePlan(**snap["plan"])
    actions = _human_actions(ledger, snap.get("human_actions", []))
    kept_decisions = [d for d in decisions if d.obligation_id not in dropped]
    reqs = assemble(kept_decisions, obligations, store, snap["include_uncertain"])
    ctx = OutputContext(store=store, versions=load_index(settings.index_path), profile=profile, plan=plan,
                        obligations=obligations, decisions=kept_decisions, human_actions=actions)
    kept, lineages, _ = output_gate(reqs, ctx)
    kept, lineages = apply_requirement_pins(kept, lineages, actions)
    submission = to_submission(kept, snap["team_id"], snap["case_id"])
    for name, data in (("requirements.json", [r.model_dump() for r in kept]),
                       ("lineage.json", [l.model_dump() for l in lineages]),
                       ("submission.json", submission)):
        if not _same(run_dir / name, data):
            problems.append(f"{name} differs from what the ledger reproduces")
    exports = [r for r in ledger.records() if r.kind == "export" and "submission_sha256" in r.meta]
    if exports and (run_dir / "submission.json").exists():
        if exports[-1].meta.get("submission_sha256") != file_sha256(run_dir / "submission.json"):
            problems.append("submission.json does not match the hash recorded at export")
    return problems
