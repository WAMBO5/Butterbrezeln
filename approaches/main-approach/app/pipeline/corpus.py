"""Corpus build (design spec section 9.1): parse the text (free), then write regulation cards and
pre-fill obligations (paid, only when asked). Idempotent: unchanged files and existing cards are
skipped unless `force` is set."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.agents.grounding_verifier import build_grounding_prompt, create_grounding_verifier
from app.agents.regulation_profiler import build_profiler_prompt, create_regulation_profiler
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.corpus.cards import CardPayload, CardStore
from app.corpus.index import load_index, version_key
from app.corpus.store import BuildStats, CorpusStore
from app.gates.card_gate import card_claims, card_gate
from app.llm import LLM, Budget, load_prices
from app.models import RegulationCard
from app.pipeline.calls import bind_call, gather_limited
from app.pipeline.loop import LoopSpec, run_verified


@dataclass
class CorpusBuildReport:
    stats: BuildStats
    cards_written: list[str] = field(default_factory=list)
    cards_failed: list[str] = field(default_factory=list)
    prefilled: int = 0
    cards_unresolved: list[str] = field(default_factory=list)
    extracted: list[str] = field(default_factory=list)
    cost_usd: float = 0.0


def card_loop(settings: Settings) -> LoopSpec[RegulationCard]:
    return LoopSpec(
        name="regulation_card", producer=create_regulation_profiler(settings), output_schema=RegulationCard,
        build_prompt=build_profiler_prompt, gate=card_gate, verifier=create_grounding_verifier(settings),
        build_review_prompt=lambda payload, card: build_grounding_prompt(card_claims(payload, card)),
        max_retries=settings.max_retries,
    )


def make_llm(settings: Settings) -> LLM:
    return LLM(settings, budget=Budget(settings.max_cost_usd, load_prices(settings.prices_path)))


async def build_corpus(settings: Settings, *, cards: bool, prefill: bool, force: bool, extract_missing: bool,
                       llm: LLM | None = None) -> CorpusBuildReport:
    report = CorpusBuildReport(stats=BuildStats())
    if extract_missing:
        from app.corpus.pdf_text import extract_missing_texts

        report.extracted = extract_missing_texts(settings)
    store = CorpusStore(settings.catalog_path)
    versions = load_index(settings.index_path)
    stats = store.build(versions, settings.text_root)
    report.stats = BuildStats(parsed=sorted(stats.parsed), unchanged=sorted(stats.unchanged),
                              missing=sorted(stats.missing))
    if not cards and not prefill:
        return report

    run_dir = settings.data_dir / "corpus_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    ledger = Ledger(run_dir)
    llm = llm or make_llm(settings)
    call = bind_call(llm, ledger)
    if cards:
        card_store = CardStore(settings.cards_dir)
        todo = [v for v in versions if v.role == "base" and store.has_text(v.regulation, v.version_label)
                and (force or card_store.load(v.regulation, v.version_label) is None)]
        loop = card_loop(settings)
        results = await gather_limited([run_verified(loop, CardPayload(store, v), call, ledger) for v in todo],
                                       settings.concurrency)
        for v, res in zip(todo, results):
            key = version_key(v.regulation, v.version_label)
            if res.output is None:
                report.cards_failed.append(key)
                continue
            card_store.save(res.output)
            report.cards_written.append(key)
            if not res.resolved:
                report.cards_unresolved.append(key)
    if prefill:
        from app.pipeline.extraction import prefill_obligations

        report.prefilled = await prefill_obligations(store, settings, call, ledger)
    report.cost_usd = round(llm.budget.spent_usd, 4) if isinstance(llm.budget, Budget) else 0.0
    report.cards_written.sort()
    report.cards_failed.sort()
    return report
