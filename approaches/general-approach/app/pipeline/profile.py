"""Product analysis loop: `product_analyst` → profile gate → `profile_verifier`."""

from __future__ import annotations

from app.agents.product_analyst import build_analyst_prompt, create_product_analyst
from app.agents.profile_verifier import build_profile_review_prompt, create_profile_verifier
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.gates.profile_gate import profile_gate
from app.models import CaseInput, ProductProfile
from app.pipeline.calls import AgentCall
from app.pipeline.loop import LoopResult, LoopSpec, run_verified


def profile_loop(settings: Settings) -> LoopSpec[ProductProfile]:
    return LoopSpec(name="product_profile", producer=create_product_analyst(settings), output_schema=ProductProfile,
                    build_prompt=build_analyst_prompt, gate=profile_gate, verifier=create_profile_verifier(settings),
                    build_review_prompt=build_profile_review_prompt, max_retries=settings.max_retries)


async def analyze_product(case: CaseInput, settings: Settings, call: AgentCall,
                          ledger: Ledger | None) -> LoopResult[ProductProfile]:
    return await run_verified(profile_loop(settings), case, call, ledger)
