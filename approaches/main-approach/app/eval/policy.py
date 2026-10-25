"""Replay a recorded run's decisions under a submit policy and the current code filters (free)."""

from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.corpus.store import CorpusStore
from app.matching.assemble import assemble
from app.matching.collect import is_administrative
from app.matching.submission import to_submission
from app.models import Requirement
from app.pipeline.state import RunState


def simulate(run_dir: Path, store: CorpusStore, settings: Settings, policy: str) -> tuple[list[Requirement], dict]:
    """The requirements and submission the run would give under `policy` ("strict" or "recall")."""
    state = RunState.load(run_dir)
    regulation_state = {d.regulation: d.state for d in state.plan.decisions} if state.plan else {}
    keep = []
    for d in state.decisions:
        ob = state.obligations.get(d.obligation_id)
        p = store.get(ob.provision_id) if ob else None
        if p is None or is_administrative(p):
            continue
        if policy == "strict" and (regulation_state.get(p.regulation) != "applicable" or d.reason == "no decision"):
            continue
        keep.append(d)
    reqs = assemble(keep, state.obligations, store, policy == "recall")
    return reqs, to_submission(reqs, settings.team_id, state.case_id)
