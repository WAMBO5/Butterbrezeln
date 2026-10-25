"""Extraction loops: provisions → cached, optionally verified obligations (design spec 6.2, 9.1)."""

from __future__ import annotations

from dataclasses import replace

from app.agents.extraction_verifier import build_extraction_review_prompt, create_extraction_verifier
from app.agents.obligation_extractor import build_extraction_prompt, create_obligation_extractor
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.corpus.obligations import ObligationCache
from app.corpus.store import CorpusStore
from app.gates.extraction_gate import extraction_gate, item_issues
from app.llm import AgentOutputError
from app.matching.extraction import ExtractionBatch, make_extraction_batches
from app.models import ExtractionOutput, Issue, Obligation, ProvisionObligations, Review
from app.pipeline.calls import AgentCall, gather_limited
from app.pipeline.loop import LoopSpec, run_verified

BATCH_SIZE = 8  # provisions per extractor call: dense tables at 15 overran the output limit (dev run, 10 of 108 calls)


def extraction_loop(settings: Settings) -> LoopSpec[ExtractionOutput]:
    return LoopSpec(name="obligation_extraction", producer=create_obligation_extractor(settings),
                    output_schema=ExtractionOutput, build_prompt=build_extraction_prompt, gate=extraction_gate,
                    verifier=None, build_review_prompt=None, max_retries=settings.max_retries)


async def _extract(batch: ExtractionBatch, cache: ObligationCache, settings: Settings, call: AgentCall,
                   ledger: Ledger | None, feedback: list[Issue]) -> list[str]:
    """Extract `batch` and cache every item that passes the gate; returns the provision ids given up.
    A batch that produced no output at all (truncated or unparsable) is retried in halves, down to one
    provision per call, so one long provision cannot sink the rest of its batch."""
    by_id = {p.provision_id: p for p in batch.provisions}
    valid: dict[str, ProvisionObligations] = {}

    def gate(b: ExtractionBatch, out: ExtractionOutput) -> list[Issue]:
        # keep each provision's latest item that passes on its own, from whichever attempt produced it,
        # so a retry that answers one issue and makes another cannot lose a provision
        for item in out.items:
            if item.provision_id in by_id and not item_issues(b, item):
                valid[item.provision_id] = item
        return extraction_gate(b, out)

    spec = replace(extraction_loop(settings), gate=gate)
    if feedback:
        initial = list(feedback)
        spec = replace(spec, build_prompt=lambda b, fb: build_extraction_prompt(b, fb or initial))
    result = await run_verified(spec, batch, call, ledger)
    output = result.output or result.last_output
    budget_spent = any(i.type == "budget" for i in result.open_issues)
    if output is None and not valid and len(batch.provisions) > 1 and not budget_spent:
        mid = (len(batch.provisions) + 1) // 2
        given_up: list[str] = []
        for half in (batch.provisions[:mid], batch.provisions[mid:]):
            ids = {p.provision_id for p in half}
            given_up += await _extract(ExtractionBatch(batch.section_id, half, batch.definitions), cache, settings,
                                       call, ledger, [i for i in feedback if i.target_id.split("/")[0] in ids])
        return given_up
    for pid, item in valid.items():
        cache.put(by_id[pid], item)
    return [pid for pid in by_id if pid not in valid]


async def extract_verified(batch: ExtractionBatch, cache: ObligationCache, settings: Settings, call: AgentCall,
                           ledger: Ledger | None, verify: bool) -> list[Obligation]:
    """The obligations of every provision in `batch`: from the cache, extracting the misses; with
    `verify`, unverified obligations are checked once and the provisions with issues re-extracted."""
    missing = [p for p in batch.provisions if cache.get(p) is None]
    if missing:
        await _extract(ExtractionBatch(batch.section_id, missing, batch.definitions), cache, settings, call, ledger, [])
    if verify:
        obligations = [o for p in batch.provisions for o in (cache.get(p) or [])]
        todo = cache.unverified([o.obligation_id for o in obligations])
        if todo:
            todo_set = set(todo)
            checked = [o for o in obligations if o.obligation_id in todo_set]
            provisions = [p for p in batch.provisions if any(o.provision_id == p.provision_id for o in checked)]
            sub = ExtractionBatch(batch.section_id, provisions, batch.definitions)
            try:
                review = await call(create_extraction_verifier(settings), build_extraction_review_prompt(sub, checked))
            except AgentOutputError:
                review = None
            if isinstance(review, Review):
                if ledger is not None:
                    ledger.append("review", "extraction_verifier", {"section_id": batch.section_id}, review,
                                  {"verdict": review.verdict})
                flagged: dict[str, list[Issue]] = {}
                if review.verdict == "retry":
                    for issue in review.issues:
                        pid = issue.target_id.split("/")[0]
                        if pid in {p.provision_id for p in provisions}:
                            flagged.setdefault(pid, []).append(issue)
                cache.mark_verified([o.obligation_id for o in checked if o.provision_id not in flagged])
                if flagged:
                    redo = [p for p in provisions if p.provision_id in flagged]
                    feedback = [i for pid in flagged for i in flagged[pid]]
                    await _extract(ExtractionBatch(batch.section_id, redo, batch.definitions), cache, settings, call,
                                   ledger, feedback)
                    cache.mark_verified([o.obligation_id for p in redo for o in (cache.get(p) or [])])
    return [o for p in batch.provisions for o in (cache.get(p) or [])]


async def prefill_obligations(store: CorpusStore, settings: Settings, call: AgentCall, ledger: Ledger | None) -> int:
    """Extract (without verification) every extractable provision of every base version."""
    cache = ObligationCache(settings.obligations_path)
    batches = []
    for v in store.versions():
        if v.role == "base":
            batches += make_extraction_batches(store.provisions(v.regulation, v.version_label), store, BATCH_SIZE)
    results = await gather_limited(
        [extract_verified(b, cache, settings, call, ledger, verify=False) for b in batches], settings.concurrency)
    return sum(len(r) for r in results)


async def reextract(batch: ExtractionBatch, cache: ObligationCache, settings: Settings, call: AgentCall,
                    ledger: Ledger | None, feedback: list[Issue]) -> list[str]:
    """Extract `batch` again with `feedback` (the output auditor's issues); returns ids given up."""
    return await _extract(batch, cache, settings, call, ledger, feedback)
