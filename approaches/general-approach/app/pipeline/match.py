"""Matching loop: `requirement_matcher` → match gate → `match_reviewer` → resolved decisions."""

from __future__ import annotations

from app.agents.match_reviewer import build_match_review_prompt, create_match_reviewer
from app.agents.requirement_matcher import build_match_prompt, create_requirement_matcher
from app.compliance.ledger import Ledger
from app.config.settings import Settings
from app.gates.match_gate import match_gate
from app.matching.match import MatchInput, resolve
from app.models import GroupMatchBatch, MatchDecision
from app.pipeline.calls import AgentCall
from app.pipeline.loop import LoopSpec, run_verified


def disputed(batch: MatchInput, out: GroupMatchBatch) -> bool:
    """A batch with a not_applicable or uncertain decision: the decisions that can lose recall."""
    return any(d.state != "applicable" for d in out.decisions)


def match_loop(settings: Settings) -> LoopSpec[GroupMatchBatch]:
    return LoopSpec(name="requirement_match", producer=create_requirement_matcher(settings), output_schema=GroupMatchBatch,
                    build_prompt=build_match_prompt, gate=match_gate, verifier=create_match_reviewer(settings),
                    build_review_prompt=build_match_review_prompt, max_retries=settings.max_retries,
                    needs_review=disputed if settings.cost_mode == "reduced" else None)


async def match_verified(batch: MatchInput, settings: Settings, call: AgentCall,
                         ledger: Ledger | None) -> list[MatchDecision]:
    return resolve(batch, await run_verified(match_loop(settings), batch, call, ledger))
