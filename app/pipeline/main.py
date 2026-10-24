"""The main run (design spec section 9.2): a fixed order of steps, driven by code.

load_case → analyze → scope → collect → extract → match → assemble → markets → finalize.
`RunState` is saved after every step; in assisted mode the run stops at checkpoints C1–C3 and
`app.pipeline.oversight.resume_run` continues it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.agents.factory import AGENT_MODEL_IDS, INSTRUCTIONS
from app.agents.output_auditor import build_output_audit_prompt, create_output_auditor
from app.compliance.ledger import Ledger
from app.compliance.manifest import Manifest, file_sha256, git_commit, prompt_version, write_manifest
from app.compliance.provenance import provenance
from app.compliance.trace import Trace
from app.config.settings import Settings
from app.corpus.cards import CardStore
from app.corpus.index import load_index, text_path, version_key
from app.corpus.obligations import EXTRACTOR_VERSION, ObligationCache
from app.corpus.store import CorpusStore
from app.gates.output_gate import OutputContext, output_gate
from app.gates.scope_gate import KEPT, ScopeContext
from app.llm import LLM, AgentOutputError, Budget, load_prices
from app.matching.assemble import assemble
from app.matching.case_loader import load_case
from app.matching.collect import SectionCandidates, collect_candidates
from app.matching.extraction import make_extraction_batches
from app.matching.match import make_match_batches
from app.matching.repair import apply_output_review
from app.matching.submission import score_submission, to_submission, validate_submission
from app.models import CaseInput, Issue, MatchDecision, Obligation, RegulationCard, RegulationVersion, Review
from app.pipeline.calls import AgentCall, bind_call, gather_limited
from app.pipeline.extraction import BATCH_SIZE, extract_verified, reextract
from app.pipeline.match import match_verified
from app.pipeline.profile import analyze_product
from app.pipeline.scope import narrow_scope, placeholder_card
from app.pipeline.state import RunState
from app.tools.corpus_tools import bind_store

MATCH_BATCH_SIZE = 40
STEPS = ("load_case", "analyze", "scope", "collect", "extract", "match", "assemble", "markets", "finalize")
CHECKPOINT_AFTER = {"analyze": "C1_profile", "scope": "C2_scope", "assemble": "C3_requirements"}


@dataclass
class RunDeps:
    settings: Settings
    store: CorpusStore
    cards: list[RegulationCard]
    cache: ObligationCache
    versions: list[RegulationVersion]
    missing_texts: list[str] = field(default_factory=list)

    @property
    def base_versions(self) -> list[RegulationVersion]:
        return [v for v in self.versions if v.role == "base"]

    @classmethod
    def load(cls, settings: Settings) -> RunDeps:
        """Open (and, for changed text files, rebuild) the corpus; cards fall back to placeholders."""
        store = CorpusStore(settings.catalog_path)
        versions = load_index(settings.index_path)
        stats = store.build(versions, settings.text_root)
        card_store = CardStore(settings.cards_dir)
        cards = [card_store.load(v.regulation, v.version_label) or placeholder_card(v)
                 for v in versions if v.role == "base"]
        return cls(settings=settings, store=store, cards=cards, cache=ObligationCache(settings.obligations_path),
                   versions=versions, missing_texts=sorted(stats.missing))


@dataclass
class RunRequest:
    case_dir: str
    markets: list[str]
    mode: Literal["benchmark", "assisted"]
    run_dir: str | None = None


@dataclass
class RunResult:
    run_dir: str
    submission_path: str | None
    partial: bool
    stopped: bool
    validation_problems: list[str]
    cost_usd: float
    missing_texts: list[str]
    status: str = "done"
    checkpoint: str | None = None


@dataclass
class RunContext:
    state: RunState
    deps: RunDeps
    llm: LLM
    ledger: Ledger
    call: AgentCall
    case: CaseInput

    @property
    def settings(self) -> Settings:
        return self.deps.settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issues(issues: list[Issue]) -> list[dict]:
    return [i.model_dump() for i in issues]


# --- steps --------------------------------------------------------------------------------------


async def step_load_case(rc: RunContext) -> None:
    rc.ledger.append("note", "orchestrator", {"case_dir": rc.state.case_dir}, None,
                     {"case_id": rc.case.case_id, "has_spec": rc.case.spec_text is not None,
                      "drawings": [p.name for p in rc.case.image_paths], "mode": rc.state.mode})


async def step_analyze(rc: RunContext) -> None:
    result = await analyze_product(rc.case, rc.settings, rc.call, rc.ledger)
    rc.state.profile = result.output
    rc.state.profile_loop = result.summary()
    if not result.resolved:
        rc.state.give_ups.append(f"product_profile: {'; '.join(i.reason for i in result.open_issues)[:300]}")
    if result.output is None:
        rc.state.error = "no product profile could be produced"


async def step_scope(rc: RunContext) -> None:
    from app.compliance.oversight import apply_pinned

    ctx = ScopeContext(profile=rc.state.profile, versions=rc.deps.base_versions, cards=rc.deps.cards,
                       store=rc.deps.store)
    result, hits = await narrow_scope(ctx, rc.settings, rc.call, rc.ledger)
    rc.state.scope_loop = result.summary()
    rc.state.safety_hits = [h.__dict__ for h in hits[:60]]
    if not result.resolved:
        rc.state.give_ups.append(f"scope_plan: {'; '.join(i.reason for i in result.open_issues)[:300]}")
    rc.state.plan = apply_pinned(result.output, rc.state.human_actions) if result.output else None
    if rc.state.plan is None:
        rc.state.error = "no scope plan could be produced"


def candidates(rc: RunContext) -> list[SectionCandidates]:
    return collect_candidates(rc.deps.store, rc.state.plan)


async def step_collect(rc: RunContext) -> None:
    rc.state.candidates = [{"part_id": c.part_id, "regulation": c.regulation, "section_id": c.section_id,
                            "provision_ids": [p.provision_id for p in c.provisions]} for c in candidates(rc)]


async def step_extract(rc: RunContext) -> None:
    unique = {p.provision_id: p for c in candidates(rc) for p in c.provisions}
    batches = make_extraction_batches(list(unique.values()), rc.deps.store, BATCH_SIZE)
    results = await gather_limited(
        [extract_verified(b, rc.deps.cache, rc.settings, rc.call, rc.ledger, verify=True) for b in batches],
        rc.settings.concurrency)
    rc.state.obligations = {o.obligation_id: o for r in results for o in r}
    missed = [pid for pid, p in unique.items() if rc.deps.cache.get(p) is None]
    if missed:
        rc.state.give_ups.append(f"extraction: {len(missed)} provisions could not be extracted "
                                 f"(e.g. {', '.join(missed[:5])})")


def _by_provision(obligations: dict[str, Obligation]) -> dict[str, list[Obligation]]:
    out: dict[str, list[Obligation]] = {}
    for o in obligations.values():
        out.setdefault(o.provision_id, []).append(o)
    return out


async def _match(rc: RunContext, cands: list[SectionCandidates], obligations: dict[str, Obligation]) -> list[MatchDecision]:
    batches = make_match_batches(cands, _by_provision(obligations), rc.state.profile, rc.deps.cards, rc.deps.store,
                                 MATCH_BATCH_SIZE)
    results = await gather_limited([match_verified(b, rc.settings, rc.call, rc.ledger) for b in batches],
                                   rc.settings.concurrency)
    return [d for r in results for d in r]


async def step_match(rc: RunContext) -> None:
    rc.state.decisions = await _match(rc, candidates(rc), rc.state.obligations)
    no_decision = sum(1 for d in rc.state.decisions if d.reason == "no decision")
    if no_decision:
        rc.state.give_ups.append(f"matching: {no_decision} obligations got no decision and are uncertain")


def _gate(rc: RunContext, dropped: set[str]):
    decisions = [d for d in rc.state.decisions if d.obligation_id not in dropped]
    reqs = assemble(decisions, rc.state.obligations, rc.deps.store, rc.settings.include_uncertain)
    ctx = OutputContext(store=rc.deps.store, versions=rc.deps.versions, profile=rc.state.profile,
                        plan=rc.state.plan, obligations=rc.state.obligations, decisions=decisions,
                        human_actions=rc.state.human_actions)
    kept, lineages, issues = output_gate(reqs, ctx)
    rc.ledger.append("gate", "gate:output", None, None, {"assembled": len(reqs), "kept": len(kept),
                                                         "issues": _issues(issues)})
    return kept, lineages, issues


async def step_assemble(rc: RunContext) -> None:
    from app.compliance.oversight import apply_requirement_pins

    kept, lineages, issues = _gate(rc, set())
    review: Review | None = None
    if kept:
        try:
            review = await rc.call(create_output_auditor(rc.settings), build_output_audit_prompt(kept))
        except AgentOutputError as exc:
            rc.state.give_ups.append(f"output_auditor: {exc.message[:200]}")
    dropped: set[str] = set()
    if isinstance(review, Review):
        rc.ledger.append("review", "output_auditor", None, review, {"verdict": review.verdict})
        rc.state.output_review = review.model_dump()
        if review.verdict == "retry" and review.issues:
            plan = apply_output_review(kept, review)
            by_id = {r.id: r for r in kept}
            dropped = {oid for rid in plan.dropped for oid in by_id[rid].obligation_ids}
            if plan.reextract:
                await _repair(rc, plan.reextract, review, kept)
            kept, lineages, issues2 = _gate(rc, dropped)
            issues = issues + issues2
    rc.state.requirements, rc.state.lineage = apply_requirement_pins(kept, lineages, rc.state.human_actions)
    rc.state.output_issues = issues


async def _repair(rc: RunContext, provision_ids: list[str], review: Review, kept: list) -> None:
    """Re-extract merged or unclear provisions with the auditor's issues, then re-match them."""
    reasons: dict[str, list[Issue]] = {}
    req_provisions = {r.id: [oid.rsplit("/", 1)[0] for oid in r.obligation_ids] for r in kept}
    for issue in review.issues:
        for pid in req_provisions.get(issue.target_id, []):
            reasons.setdefault(pid, []).append(issue.model_copy(update={"target_id": pid}))
    provisions = [p for p in (rc.deps.store.get(pid) for pid in provision_ids) if p is not None]
    for batch in make_extraction_batches(provisions, rc.deps.store, BATCH_SIZE):
        feedback = [i for p in batch.provisions for i in reasons.get(p.provision_id, [])]
        await reextract(batch, rc.deps.cache, rc.settings, rc.call, rc.ledger, feedback)
    redo = set(provision_ids)
    rc.state.obligations = {k: o for k, o in rc.state.obligations.items() if o.provision_id not in redo}
    for p in provisions:
        for o in rc.deps.cache.get(p) or []:
            rc.state.obligations[o.obligation_id] = o
    fresh = {k: o for k, o in rc.state.obligations.items() if o.provision_id in redo}
    cands = [SectionCandidates(c.part_id, c.regulation, c.version_label, c.section_id, c.heading_path,
                               [p for p in c.provisions if p.provision_id in redo]) for c in candidates(rc)]
    new_decisions = await _match(rc, [c for c in cands if c.provisions], fresh)
    rc.state.decisions = [d for d in rc.state.decisions if d.obligation_id.rsplit("/", 1)[0] not in redo] + new_decisions


async def step_markets(rc: RunContext) -> None:
    from app.pipeline.markets import run_markets_step

    await run_markets_step(rc)


async def step_finalize(rc: RunContext) -> None:
    from app.report import render_report

    state, settings, run_dir = rc.state, rc.settings, Path(rc.state.run_dir)
    budget = rc.llm.budget if isinstance(rc.llm.budget, Budget) else None
    state.cost = budget.report() if budget else {}
    state.partial = bool(budget and budget.exceeded)
    models = {name: row["model"] for name, row in (budget.per_agent if budget else {}).items()}
    submission = to_submission(state.requirements, settings.team_id, state.case_id)
    state.validation_problems = validate_submission(submission, settings)
    expected = Path(state.case_dir) / "expected.json"
    state.score = score_submission(submission, expected, settings) if expected.exists() else None
    state.stage_counts = stage_counts(state, rc.deps)
    review = _review_record(run_dir)

    def dump(name: str, data: object) -> None:
        (run_dir / name).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    dump("profile.json", state.profile.model_dump() if state.profile else None)
    dump("scope_plan.json", state.plan.model_dump() if state.plan else None)
    dump("requirements.json", [r.model_dump() for r in state.requirements])
    dump("lineage.json", [l.model_dump() for l in state.lineage])
    dump("submission.json", submission)
    dump("submission.provenance.json", provenance(state.run_id, state.mode, models, review))
    if state.markets_result is not None:
        dump("markets.json", state.markets_result.get("markets"))
        dump("ship_plan.json", state.markets_result.get("ship_plan"))
    state.finished_at = _now()
    write_manifest(run_dir, build_manifest(state, rc.deps, models, review))
    (run_dir / "report.md").write_text(render_report(state, models), encoding="utf-8")
    rc.ledger.append("export", "orchestrator", None, submission, {
        "files": sorted(p.name for p in run_dir.iterdir() if p.is_file()),
        "submission_sha256": file_sha256(run_dir / "submission.json"), "requirements": len(state.requirements),
        "validation_problems": len(state.validation_problems), "partial": state.partial})


def _review_record(run_dir: Path) -> dict | None:
    path = run_dir / "signoff.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def stage_counts(state: RunState, deps: RunDeps) -> dict:
    kept = [d for d in state.plan.decisions if d.state in KEPT] if state.plan else []
    sections = {sid for d in kept for ps in d.sections for sid in ps.section_ids}
    provisions = {pid for c in state.candidates for pid in c["provision_ids"]}
    return {"regulations": len(deps.base_versions), "kept_regulations": len(kept), "sections": len(sections),
            "candidate_provisions": len(provisions), "obligations": len(state.obligations),
            "decisions": len(state.decisions),
            "applicable_decisions": sum(1 for d in state.decisions if d.state == "applicable"),
            "uncertain_decisions": sum(1 for d in state.decisions if d.state == "uncertain"),
            "requirements": len(state.requirements)}


def build_manifest(state: RunState, deps: RunDeps, models: dict[str, str], review: dict | None) -> Manifest:
    settings = deps.settings
    case_dir = Path(state.case_dir)
    inputs = {p.name: file_sha256(p) for p in sorted(case_dir.iterdir()) if p.is_file() and p.name != "expected.json"}
    corpus_files = {}
    for v in deps.versions:
        path = text_path(settings.text_root, v.regulation, v.role)
        if path.exists():
            corpus_files[version_key(v.regulation, v.version_label)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return Manifest(
        run_id=state.run_id, mode=state.mode, started_at=state.started_at, finished_at=state.finished_at,
        git_commit=git_commit(),
        settings={"models": {"judgment": settings.model_judgment, "fast": settings.model_fast,
                             "review": settings.model_review},
                  "max_retries": settings.max_retries, "max_cost_usd": settings.max_cost_usd,
                  "include_uncertain": settings.include_uncertain, "concurrency": settings.concurrency,
                  "fake_llm": settings.fake_llm, "retention_days": settings.retention_days},
        inputs=inputs,
        corpus={"index_sha256": file_sha256(settings.index_path), "text_sha256": corpus_files,
                "cards": sorted(c.regulation for c in deps.cards if c.evidence[:1] != ["no card: decide from the title and the tools"]),
                "extractor_version": EXTRACTOR_VERSION, "missing_texts": deps.missing_texts},
        prompt_versions={name: prompt_version(text) for name, text in sorted(INSTRUCTIONS.items())},
        models=models or {k: v for k, v in AGENT_MODEL_IDS.items()},
        cost=state.cost, review=review,
    )


STEP_FUNCS: dict[str, Callable[[RunContext], Awaitable[None]]] = {
    "load_case": step_load_case, "analyze": step_analyze, "scope": step_scope, "collect": step_collect,
    "extract": step_extract, "match": step_match, "assemble": step_assemble, "markets": step_markets,
    "finalize": step_finalize,
}


# --- driver -------------------------------------------------------------------------------------


def make_run_llm(settings: Settings, state: RunState, listeners: list | None) -> LLM:
    budget = Budget(settings.max_cost_usd, load_prices(settings.prices_path))
    if state.cost:
        budget.spent_usd = float(state.cost.get("spent_usd", 0.0))
        budget.per_agent = dict(state.cost.get("per_agent", {}))
    trace = Trace(Path(state.run_dir) / "trace.jsonl", list(listeners or []))
    return LLM(settings, budget=budget, listeners=[trace])


async def drive(state: RunState, deps: RunDeps, listeners: list | None = None) -> RunResult:
    """Run the steps after `state.step`, saving after each; stop at a checkpoint in assisted mode."""
    bind_store(deps.store)
    llm = make_run_llm(deps.settings, state, listeners)
    ledger = Ledger(Path(state.run_dir))
    rc = RunContext(state=state, deps=deps, llm=llm, ledger=ledger, call=bind_call(llm, ledger),
                    case=load_case(Path(state.case_dir)))
    state.status, state.checkpoint = "running", None
    start = 0 if state.step is None else STEPS.index(state.step) + 1
    try:
        for name in STEPS[start:]:
            if (state.stopped or state.error) and name not in ("finalize",):
                continue
            for listener in llm.listeners:
                listener({"event": "step_start", "step": name})
            await STEP_FUNCS[name](rc)
            state.step = name
            if isinstance(llm.budget, Budget):
                state.cost = llm.budget.report()
                state.partial = llm.budget.exceeded
            state.save()
            for listener in llm.listeners:
                listener({"event": "step_end", "step": name})
            if state.mode == "assisted" and name in CHECKPOINT_AFTER and not state.error and not state.stopped:
                state.status, state.checkpoint = "awaiting_review", CHECKPOINT_AFTER[name]
                state.save()
                ledger.append("note", "orchestrator", None, None, {"checkpoint": state.checkpoint})
                return result_of(state)
    except Exception as exc:
        state.status, state.error = "failed", f"{type(exc).__name__}: {exc}"
        state.save()
        raise
    state.status = "stopped" if state.stopped else ("failed" if state.error else "done")
    state.save()
    return result_of(state)


def result_of(state: RunState) -> RunResult:
    run_dir = Path(state.run_dir)
    submission = run_dir / "submission.json"
    return RunResult(run_dir=str(run_dir), submission_path=str(submission) if submission.exists() else None,
                     partial=state.partial, stopped=state.stopped, validation_problems=state.validation_problems,
                     cost_usd=float(state.cost.get("spent_usd", 0.0)) if state.cost else 0.0,
                     missing_texts=state.missing_texts, status=state.status, checkpoint=state.checkpoint)


def new_run_id(case_id: str) -> str:
    return f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}Z-{case_id}"


def create_run(case_dir: Path, *, markets: list[str], mode: str, settings: Settings, run_dir: Path | None,
               deps: RunDeps) -> RunState:
    """Validate the case (raises `CaseError`) and write the initial run state."""
    case = load_case(Path(case_dir))
    run_id = new_run_id(case.case_id)
    target = Path(run_dir) if run_dir else settings.runs_dir / run_id
    state = RunState(run_id=run_id, run_dir=str(target), case_dir=str(Path(case_dir)), case_id=case.case_id,
                     markets=list(markets), mode=mode, started_at=_now(), missing_texts=deps.missing_texts)
    state.save()
    return state


async def run_case(case_dir: Path, *, markets: list[str], mode: str, settings: Settings, run_dir: Path | None,
                   listeners: list | None = None, deps: RunDeps | None = None) -> RunResult:
    deps = deps or RunDeps.load(settings)
    state = create_run(case_dir, markets=markets, mode=mode, settings=settings, run_dir=run_dir, deps=deps)
    return await drive(state, deps, listeners)
