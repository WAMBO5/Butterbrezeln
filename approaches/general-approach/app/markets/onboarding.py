"""Onboard a market from source files: `market_onboarding` → market gate → `grounding_verifier`,
then the profile is written to `data/markets/<market_id>.yaml`."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.agents.grounding_verifier import build_grounding_prompt, create_grounding_verifier
from app.agents.market_onboarding import build_onboarding_prompt, create_market_onboarding
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.corpus.index import load_index
from app.gates.market_gate import SourceDoc, market_claims, market_gate  # noqa: F401  (SourceDoc re-exported)
from app.models import MarketProfile
from app.pipeline.calls import AgentCall
from app.pipeline.loop import LoopSpec, run_verified

SAMPLE_MARK = "ILLUSTRATIVE SAMPLE"


class OnboardingError(Exception):
    pass


def read_source(path: Path) -> SourceDoc:
    text = Path(path).read_text(encoding="utf-8")
    first = text.lstrip().splitlines()[0].strip() if text.strip() else ""
    return SourceDoc(document_id=Path(path).stem, text=text, sample=first == SAMPLE_MARK)


def market_id_for(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_") or "market"


async def onboard_market(name: str, source_files: list[Path], settings: Settings, call: AgentCall,
                         ledger: Ledger | None) -> MarketProfile:
    sources = [read_source(p) for p in source_files]
    versions = load_index(settings.index_path)
    loop = LoopSpec(name="market_profile", producer=create_market_onboarding(settings), output_schema=MarketProfile,
                    build_prompt=lambda srcs, fb: build_onboarding_prompt(name, versions, srcs, fb),
                    gate=lambda srcs, prof: market_gate(srcs, versions, prof),
                    verifier=create_grounding_verifier(settings),
                    build_review_prompt=lambda srcs, prof: build_grounding_prompt(market_claims(srcs, prof)),
                    max_retries=settings.max_retries)
    result = await run_verified(loop, sources, call, ledger)
    if result.output is None:
        raise OnboardingError("; ".join(i.reason for i in result.open_issues) or "no market profile produced")
    profile = result.output.model_copy(update={"market_id": market_id_for(name), "name": name,
                                               "illustrative": result.output.illustrative or any(s.sample for s in sources)})
    settings.markets_dir.mkdir(parents=True, exist_ok=True)
    data = profile.model_dump(mode="json")
    data["unresolved_issues"] = [i.model_dump() for i in result.open_issues]
    (settings.markets_dir / f"{profile.market_id}.yaml").write_text(
        "# Built by market_onboarding from cited sources. Review before use.\n" + yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8")
    return profile
